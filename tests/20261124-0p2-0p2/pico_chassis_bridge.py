"""Bridge Pico Joy messages to the Luna vendor chassis manual drive interface."""
import argparse
import asyncio
import json
import math
import time
import urllib.request
from pathlib import Path

TARGET = "6.6.7.6"
PERIOD = 0.10
JOY_TIMEOUT = 0.25
STATE_TIMEOUT = 0.40
DEADZONE = 0.15
STOP = (0.0, 0.0, 0.0)
UNSAFE_FLAGS = ("isScram", "isSoftAuto", "isPause", "isSuspend",
                "isParkingMode", "isReseting", "isFallback")


def usable_state(state):
    return (
        state.get("id") == 1
        and state.get("isNormal") is True
        and state.get("workStatus") in (9, 14)
        and all(state.get(flag) is False for flag in UNSAFE_FLAGS)
    )


def scaled_axis(value):
    value = max(-1.0, min(1.0, value))
    magnitude = max(0.0, (abs(value) - DEADZONE) / (1.0 - DEADZONE))
    return math.copysign(magnitude, value)


def signed_axis(values, axis):
    # One-based signed axes keep zero unavailable as an accidental mapping.
    value = float(values[abs(axis) - 1])
    if not math.isfinite(value) or abs(value) > 1.05:
        raise ValueError("Invalid joystick value")
    return scaled_axis(value * (1 if axis > 0 else -1))


class DriveGate:
    def __init__(self, left_forward, left_lateral, right_turn, hold_button=None):
        self.mapping = left_forward, left_lateral, right_turn, hold_button
        self.neutral_seen = False

    def reset(self):
        self.neutral_seen = False

    def command(self, left, right, permitted, linear, angular):
        if not permitted:
            self.reset()
            return STOP
        forward, lateral, turn, button = self.mapping
        try:
            x = signed_axis(left.axes, forward)
            y = signed_axis(left.axes, lateral) if lateral else 0.0
            w = signed_axis(right.axes, turn)
            held = left.buttons[button] if button is not None else 1
            if held not in (0, 1):
                raise ValueError("Invalid enable button value")
        except (AttributeError, IndexError, TypeError, ValueError):
            self.reset()
            return STOP
        if button is None and not self.neutral_seen:
            self.neutral_seen = (x, y, w) == STOP
            return STOP
        if button is not None and not held:
            self.neutral_seen = (x, y, w) == STOP
            return STOP
        if not self.neutral_seen:
            return STOP
        norm = max(1.0, math.hypot(x, y))
        return x * linear / norm, y * linear / norm, w * angular


def payload(command):
    x, y, w = command
    return json.dumps({"id": 1, "x": x, "y": y, "w": w}, allow_nan=False)


def read_limits():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(
        f"http://{TARGET}:8080/api/Config/AMR/GetParam", data=b"{}",
        headers={"Content-Type": "application/json"},
    )
    with opener.open(request, timeout=1.0) as response:
        configuration = json.load(response)
    if configuration.get("ErrorCode") != 0:
        raise ValueError("Chassis configuration read failed")
    settings = configuration["Content"]
    if settings["robot.manual_move.enable_avoid"] is not True:
        raise ValueError("Chassis manual obstacle avoidance is disabled")
    limits = tuple(float(settings[f"max_speed.{name}"]) for name in ("linear", "angular"))
    if any(not math.isfinite(limit) or limit <= 0 for limit in limits):
        raise ValueError("Invalid chassis speed limit")
    return min(limits[0], 0.20), min(limits[1], 0.20)


async def drive(node, rclpy, inputs, gate, live, trace):
    from websockets.asyncio.client import connect
    from websockets.exceptions import ConnectionClosed

    def fresh(side, now):
        data = inputs.get(side)
        return data is not None and now - data[0] <= JOY_TIMEOUT

    async with connect(f"ws://{TARGET}:6001/api/AMR/State", proxy=None,
                       open_timeout=2, close_timeout=0.3, max_queue=1) as state_socket:
        state = {}
        state_time = float("-inf")

        async def read_state():
            nonlocal state, state_time
            async for message in state_socket:
                content = json.loads(message).get("Content")
                if isinstance(content, dict) and content.get("id") == 1:
                    state, state_time = content, time.monotonic()
                    trace("feedback", velocity=content.get("linearSpeedVec3"),
                          angular=content.get("angularSpeed"),
                          work_status=content.get("workStatus"),
                          normal=content.get("isNormal"),
                          flags={key: content.get(key) for key in UNSAFE_FLAGS})

        async def drive_loop(output):
            last_command = STOP
            last_sent = 0.0
            refreshed_at = float("-inf")
            next_refresh_at = 0.0
            limits = 0.0, 0.0
            refresh = asyncio.create_task(asyncio.to_thread(read_limits))
            try:
                while rclpy.ok():
                    for _ in range(4):
                        rclpy.spin_once(node, timeout_sec=0)
                    now = time.monotonic()
                    if reader.done():
                        reader.result()
                        return
                    if refresh is None and now >= next_refresh_at:
                        refresh = asyncio.create_task(asyncio.to_thread(read_limits))
                    if refresh is not None and refresh.done():
                        try:
                            limits = refresh.result()
                        except (OSError, ValueError, KeyError, TypeError) as exc:
                            refreshed_at = float("-inf")
                            print(f"Chassis configuration unavailable: {exc}", flush=True)
                        else:
                            refreshed_at = now
                        next_refresh_at = now + 0.75
                        refresh = None
                    permitted = (
                        all(fresh(side, now) for side in ("left", "right"))
                        and inputs.get("connected", (0, False))[1] is True
                        and now - inputs["connected"][0] <= 2.0
                        and now - state_time <= STATE_TIMEOUT
                        and usable_state(state)
                        and now - refreshed_at <= 1.5
                    )
                    left = inputs.get("left", (0, None))[1]
                    right = inputs.get("right", (0, None))[1]
                    command = gate.command(left, right, permitted, *limits)
                    if command == STOP:
                        if last_command != STOP:
                            if output is not None:
                                await asyncio.wait_for(output.send(payload(STOP)), timeout=PERIOD)
                                trace("command_sent", command=STOP, permitted=permitted,
                                      neutral_seen=gate.neutral_seen)
                            print("STOP", flush=True)
                            last_command = STOP
                    elif now - last_sent >= PERIOD:
                        # Mark motion as pending before send so a failed send also attempts stop.
                        was_stopped = last_command == STOP
                        last_command = command
                        if output is not None:
                            await asyncio.wait_for(output.send(payload(command)), timeout=PERIOD)
                            trace("command_sent", command=command, permitted=permitted,
                                  left_axes=list(left.axes), right_axes=list(right.axes))
                        if output is None or was_stopped:
                            print(("LIVE " if live else "MONITOR ") + payload(command), flush=True)
                        last_sent = now
                    await asyncio.sleep(0.02)
            finally:
                if refresh is not None:
                    refresh.cancel()
                if output is not None and last_command != STOP:
                    try:
                        await asyncio.wait_for(output.send(payload(STOP)), timeout=PERIOD)
                        trace("command_sent", command=STOP, reason="exit")
                    except (OSError, TimeoutError, ConnectionClosed):
                        pass

        reader = asyncio.create_task(read_state())
        try:
            if live:
                # The vendor browser sends velocity frames, with no client-side ping.
                async with connect(f"ws://{TARGET}:6001/api/AMR/ManualMove", proxy=None,
                                   open_timeout=2, close_timeout=0.3,
                                   ping_interval=None) as output:
                    await drive_loop(output)
            else:
                await drive_loop(None)
        finally:
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left-forward", type=int, choices=(-2, 2), default=2)
    parser.add_argument("--left-lateral", type=int, choices=(-1, 0, 1), default=-1,
                        help="Use 0 if the chassis does not support strafing")
    parser.add_argument("--right-turn", type=int, choices=(-1, 1), default=-1)
    parser.add_argument("--live", action="store_true",
                        help="Enable vendor velocity output for a supervised on-site test")
    parser.add_argument("--require-stick-press", action="store_true",
                        help="Optional legacy left-stick press interlock; off by default")
    parser.add_argument("--record", type=Path,
                        help="Record each sent velocity and chassis feedback as JSONL")
    args = parser.parse_args()

    import rclpy
    from rclpy.qos import QoSProfile, ReliabilityPolicy
    from sensor_msgs.msg import Joy
    from std_msgs.msg import Bool

    inputs = {}
    rclpy.init()
    node = rclpy.create_node("pico_chassis_bridge")
    qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)

    def receive(side, value):
        inputs[side] = time.monotonic(), value

    node.create_subscription(Joy, "/control/vr_joy_L", lambda msg: receive("left", msg), qos)
    node.create_subscription(Joy, "/control/vr_joy_R", lambda msg: receive("right", msg), qos)
    node.create_subscription(Bool, "/info/vr_connected",
                             lambda msg: receive("connected", msg.data), qos)
    gate = DriveGate(args.left_forward, args.left_lateral, args.right_turn,
                     hold_button=0 if args.require_stick_press else None)
    record_file = args.record.open("a", buffering=1) if args.record else None
    def trace(event, **fields):
        if record_file is not None:
            record_file.write(json.dumps({"time": time.time(), "mono": time.monotonic(),
                                          "event": event, **fields}, allow_nan=False) + "\n")
    trace("start", live=args.live, require_stick_press=args.require_stick_press,
          mapping={"forward": args.left_forward, "lateral": args.left_lateral,
                   "turn": args.right_turn}, linear_cap=0.20, angular_cap=0.20)
    print("Joystick mode: " + ("hold left stick" if args.require_stick_press else
          "direct; center to stop; initial/reconnect centering required"), flush=True)
    print("Live velocity output enabled" if args.live else "Monitoring; no velocity output",
          flush=True)
    from websockets.exceptions import WebSocketException

    async def serve():
        while rclpy.ok():
            gate.reset()
            try:
                await drive(node, rclpy, inputs, gate, args.live, trace)
            except (OSError, TimeoutError, WebSocketException) as exc:
                print(f"Chassis connection interrupted: {exc}", flush=True)
            if rclpy.ok():
                print("Reconnecting; release and center both joysticks", flush=True)
                await asyncio.sleep(1)

    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
        trace("exit")
        if record_file is not None:
            record_file.close()


if __name__ == "__main__":
    main()

