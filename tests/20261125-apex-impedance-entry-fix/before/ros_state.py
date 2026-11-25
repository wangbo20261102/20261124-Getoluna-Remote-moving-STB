from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import rclpy
from marvin_msgs.srv import Int, JsonCommand
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Int16MultiArray, Int32, String
from std_srvs.srv import Trigger


DEFAULT_CONTROL_STATE_TOPICS = ("/info/robot_state", "/info/arm_state")


def _csv_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.environ.get(name, "")
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    return values or default


class ApexStateNode(Node):
    READY_MODES = {0, 1, 2, 3}

    def __init__(self) -> None:
        super().__init__("apex_backend_state")
        self._lock = threading.Lock()
        self._last_arm_state: list[int] | None = None
        self._last_arm_state_time: float | None = None
        self._control_ready = False
        self._set_ready_accepted = False
        self._control_error = False
        self._control_error_message = ""
        self._current_mode = -1
        self._current_speed_factor = 1.0
        self._current_input_mode = -1
        self._playback_status: dict[str, Any] = {
            "is_playing": False,
            "is_paused": False,
            "playback_rate": 1.0,
            "current_time": 0.0,
            "duration": 0.0,
            "progress": 0.0,
            "bag_path": None,
        }
        self._bag_info_cache: dict[str, Any] = {}
        username = (
            os.environ.get("SUDO_USER")
            or os.environ.get("USER")
            or os.environ.get("LOGNAME")
            or "marvin"
        )
        storage_root = os.environ.get(
            "BAG_STORAGE_ROOT", os.path.join("/media", username, "BAG_STORAGE")
        )
        self._bag_directory = os.path.join(storage_root, "recorded_bags")
        self._latest_robot_info: dict[str, Any] = {
            "robot_type": "unknown",
            "controller_version": None,
            "controller_version_text": "unknown",
            "stamp_ns": None,
            "age_sec": None,
            "received": False,
        }
        self._last_robot_info_time: float | None = None

        self.mode_client = self.create_client(Int, "/control/set_mode")
        self.ready_client = self.create_client(Trigger, "/control/set_ready")
        self.speed_client = self.create_client(Int, "/control/set_vel_ratio")
        self.home_arm_client = self.create_client(Trigger, "/control/go_home")
        self.go_home_client = self.create_client(Trigger, "/control/go_home")
        self.reset_grippers_client = self.create_client(Trigger, "/control/reset_grippers")
        self.set_input_client = self.create_client(Int, "/control/set_input")
        self.playback_control_client = self.create_client(JsonCommand, "playback/control")
        self.recorder_control_client = self.create_client(JsonCommand, "recorder/control")

        for topic in _csv_env("APEX_CONTROL_STATE_TOPICS", DEFAULT_CONTROL_STATE_TOPICS):
            self.create_subscription(
                Int16MultiArray,
                topic,
                lambda msg, source_topic=topic: self._control_state_callback(source_topic, msg),
                10,
            )
        latched_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self.create_subscription(Int32, "/control/input_mode", self._input_mode_callback, latched_qos)
        self.create_subscription(String, "/playback_status", self._playback_status_callback, 10)
        self._create_robot_info_subscription()
        self.get_logger().info("Apex backend state node started")

    def _robot_state_callback(self, msg: Int16MultiArray) -> None:
        self._control_state_callback("/info/robot_state", msg)

    def _arm_state_callback(self, msg: Int16MultiArray) -> None:
        self._control_state_callback("/info/arm_state", msg)

    def _input_mode_callback(self, msg: Int32) -> None:
        with self._lock:
            self._current_input_mode = int(msg.data)

    def _playback_status_callback(self, msg: String) -> None:
        try:
            status = json.loads(msg.data)
            with self._lock:
                self._playback_status = status
        except Exception:
            pass

    def _control_state_callback(self, source_topic: str, msg: Int16MultiArray) -> None:
        now = time.time()
        data = list(msg.data)
        ready = False
        error = False
        error_message = ""
        mode = -1

        if len(data) < 2:
            error = True
            error_message = f"{source_topic} payload too short: {len(data)}"
        else:
            mode_a, mode_b = data[:2]
            if mode_a == -1 and mode_b == -1:
                ready = False
                mode = -1
            elif mode_a == mode_b and mode_a in self.READY_MODES:
                ready = True
                mode = mode_a
            elif mode_a != mode_b:
                error = True
                error_message = f"Control state mismatch: left={mode_a}, right={mode_b}"
            else:
                error = True
                error_message = f"Invalid control state: left={mode_a}, right={mode_b}"

        with self._lock:
            self._last_arm_state = data
            self._last_arm_state_time = now
            self._control_ready = ready
            self._set_ready_accepted = ready
            self._control_error = error
            self._control_error_message = error_message
            self._current_mode = mode

    def _create_robot_info_subscription(self) -> None:
        try:
            from marvin_msgs.msg import RobotInfo
        except (ImportError, ModuleNotFoundError):
            self.get_logger().warning("marvin_msgs/msg/RobotInfo is unavailable")
            return
        self.create_subscription(RobotInfo, "/info/robot_info", self._robot_info_callback, 10)

    def _robot_info_callback(self, msg: Any) -> None:
        stamp = getattr(getattr(msg, "header", None), "stamp", None)
        stamp_ns = None
        if stamp is not None:
            stamp_ns = int(getattr(stamp, "sec", 0)) * 1_000_000_000 + int(getattr(stamp, "nanosec", 0))

        now = time.time()
        with self._lock:
            self._last_robot_info_time = now
            self._latest_robot_info = {
                "robot_type": getattr(msg, "robot_type", "unknown"),
                "controller_version": _to_int(getattr(msg, "controller_version", None)),
                "controller_version_text": getattr(msg, "controller_version_text", "unknown"),
                "stamp_ns": stamp_ns,
                "age_sec": 0.0,
                "received": True,
            }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            last_time = self._last_arm_state_time
            age = None if last_time is None else max(0.0, time.time() - last_time)
            return {
                "control_ready": self._control_ready,
                "control_error": self._control_error,
                "control_error_message": self._control_error_message,
                "arm_state": self._last_arm_state,
                "arm_state_age_sec": age,
                "current_mode": self._current_mode,
                "speed_factor": self._current_speed_factor,
                "current_input_mode": self._current_input_mode,
            }

    def robot_info_snapshot(self) -> dict[str, Any]:
        with self._lock:
            robot_info = dict(self._latest_robot_info)
            last_time = self._last_robot_info_time
        robot_info["age_sec"] = None if last_time is None else max(0.0, time.time() - last_time)
        return robot_info

    def require_robot_service_active(self, robot_status: dict[str, Any]) -> tuple[bool, str]:
        if robot_status.get("active_state") != "active":
            return False, "Robot Control service is not active"
        if robot_status.get("error"):
            return False, "Robot Control service reports a runtime error"
        return True, ""

    def set_mode(self, mode: int) -> dict[str, Any]:
        request = Int.Request()
        request.data = mode
        response = self._call(self.mode_client, request, "/control/set_mode")
        if _int_response_success(response):
            with self._lock:
                self._current_mode = mode
            return {"success": True, "mode": mode, "error_code": _response_error_code(response)}
        return _int_response_error(response)

    def set_input(self, input_id: int) -> dict[str, Any]:
        request = Int.Request()
        request.data = input_id
        response = self._call(self.set_input_client, request, "/control/set_input")
        if _int_response_success(response):
            with self._lock:
                self._current_input_mode = input_id
            return {"success": True, "input": input_id, "error_code": _response_error_code(response)}
        return _int_response_error(response)

    def set_ready(self) -> dict[str, Any]:
        response = self._call(self.ready_client, Trigger.Request(), "/control/set_ready")
        if response.success:
            with self._lock:
                self._set_ready_accepted = True
                self._control_ready = True
        return {"success": bool(response.success), "message": response.message}

    def set_vel_ratio(self, speed_factor: float) -> dict[str, Any]:
        if speed_factor < 0:
            return {"success": False, "error": "speed_factor must be greater than or equal to 0"}
        request = Int.Request()
        request.data = int(speed_factor)
        response = self._call(self.speed_client, request, "/control/set_vel_ratio")
        if _int_response_success(response):
            with self._lock:
                self._current_speed_factor = speed_factor
            return {"success": True, "speed_factor": speed_factor, "error_code": _response_error_code(response)}
        return _int_response_error(response)

    def home_arm(self) -> dict[str, Any]:
        response = self._call(self.home_arm_client, Trigger.Request(), "/control/go_home")
        return {"success": bool(response.success), "message": response.message}

    def go_home(self) -> dict[str, Any]:
        response = self._call(self.go_home_client, Trigger.Request(), "/control/go_home")
        return {"success": bool(response.success), "message": response.message}

    def reset_grippers(self) -> dict[str, Any]:
        response = self._call(self.reset_grippers_client, Trigger.Request(), "/control/reset_grippers")
        return {"success": bool(response.success), "message": response.message}

    # ── Playback ──────────────────────────────────────────────────────────────

    def get_playback_status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._playback_status)

    def playback_control(self, command: dict[str, Any]) -> dict[str, Any]:
        return self._json_command_call(
            self.playback_control_client,
            "playback/control",
            command,
            timeout_sec=10.0,
        )

    # ── Recording ─────────────────────────────────────────────────────────────

    def recorder_control(self, command: dict[str, Any]) -> dict[str, Any]:
        return self._json_command_call(
            self.recorder_control_client,
            "recorder/control",
            command,
            timeout_sec=10.0,
        )

    def get_bag_files(self) -> list[dict[str, Any]]:
        bag_files: list[dict[str, Any]] = []
        try:
            bag_dir = Path(self._bag_directory)
            if not bag_dir.exists():
                return bag_files
            for metadata_path in bag_dir.rglob("metadata.yaml"):
                rosbag_dir = metadata_path.parent
                if not rosbag_dir.is_dir():
                    continue
                try:
                    display_dir = rosbag_dir.parent if rosbag_dir.name == "data" else rosbag_dir
                    stat_info = display_dir.stat()
                    bag_data_files = list(rosbag_dir.glob("*.mcap")) or list(rosbag_dir.glob("*.db3"))
                    video_dir = display_dir / "video"
                    video_files = list(video_dir.glob("*")) if video_dir.is_dir() else []
                    total_size = sum(
                        f.stat().st_size for f in [*bag_data_files, *video_files] if f.is_file()
                    )
                    rosbag_path = str(rosbag_dir)
                    display_path = str(display_dir)
                    bag_files.append({
                        "path": rosbag_path,
                        "name": display_dir.name,
                        "size": total_size,
                        "modified_time": stat_info.st_mtime,
                        "created_time": stat_info.st_ctime,
                        "root_path": display_path,
                    })
                except Exception as exc:
                    self.get_logger().warning(f"Failed to read bag info {rosbag_dir}: {exc}")
            bag_files.sort(key=lambda x: x.get("modified_time", 0), reverse=True)
        except Exception as exc:
            self.get_logger().error(f"Failed to scan bag directory: {exc}")
        return bag_files

    def get_bag_info(self, bag_path: str, fast_mode: bool = True) -> dict[str, Any] | None:
        try:
            import yaml
            from rosbag2_py import ConverterOptions, SequentialReader, StorageOptions

            if not os.path.exists(bag_path):
                return None

            cache_key = f"{bag_path}:{fast_mode}"
            try:
                current_mtime = Path(bag_path).stat().st_mtime
            except OSError:
                return None
            if cache_key in self._bag_info_cache:
                cached_info, cached_mtime = self._bag_info_cache[cache_key]
                if cached_mtime == current_mtime:
                    return cached_info

            metadata_path = Path(bag_path) / "metadata.yaml"
            if metadata_path.exists():
                try:
                    with open(metadata_path) as f:
                        metadata = yaml.safe_load(f)
                    bag_info = metadata.get("rosbag2_bagfile_information", {})
                    topics_info = bag_info.get("topics_with_message_count", [])
                    result = {
                        "topics": [t["topic_metadata"]["name"] for t in topics_info],
                        "topic_count": len(topics_info),
                        "message_count": sum(t["message_count"] for t in topics_info),
                        "duration": bag_info.get("duration", {}).get("nanoseconds", 0) / 1e9,
                        "start_time": bag_info.get("starting_time", {}).get("nanoseconds_since_epoch", 0) / 1e9,
                    }
                    result["end_time"] = result["start_time"] + result["duration"]
                    self._bag_info_cache[cache_key] = (result, current_mtime)
                    return result
                except Exception:
                    pass

            reader = SequentialReader()
            reader.open(
                StorageOptions(uri=bag_path, storage_id="mcap"),
                ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"),
            )
            topics: set[str] = set()
            message_count = 0
            start_time = end_time = None
            while reader.has_next():
                topic, _data, ts = reader.read_next()
                topics.add(topic)
                message_count += 1
                if start_time is None or ts < start_time:
                    start_time = ts
                if end_time is None or ts > end_time:
                    end_time = ts
            duration = (end_time - start_time) / 1e9 if start_time and end_time else 0.0
            result = {
                "topics": sorted(topics),
                "topic_count": len(topics),
                "message_count": message_count,
                "duration": duration,
                "start_time": start_time / 1e9 if start_time else 0,
                "end_time": end_time / 1e9 if end_time else 0,
            }
            self._bag_info_cache[cache_key] = (result, current_mtime)
            return result
        except Exception as exc:
            self.get_logger().error(f"get_bag_info failed for {bag_path}: {exc}")
            return None

    def _json_command_call(
        self,
        client: Any,
        service_name: str,
        command: dict[str, Any],
        timeout_sec: float = 5.0,
    ) -> dict[str, Any]:
        request = JsonCommand.Request()
        request.command_json = json.dumps(command, ensure_ascii=False)
        response = self._call(client, request, service_name, timeout_sec=timeout_sec)
        if response.result_json:
            try:
                result = json.loads(response.result_json)
            except json.JSONDecodeError:
                result = {"status": "error", "error_message": response.result_json}
        else:
            result = {}
        if not response.success and result.get("status") != "error":
            result["status"] = "error"
            result["error_message"] = response.message
        return result

    def _call(self, client: Any, request: Any, service_name: str, timeout_sec: float = 2.0) -> Any:
        if not client.wait_for_service(timeout_sec=1.0):
            raise RuntimeError(f"Service unavailable: {service_name}")
        future = client.call_async(request)
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if future.done():
                return future.result()
            time.sleep(0.02)
        raise TimeoutError(f"Service call timed out: {service_name}")


class RosStateRuntime:
    def __init__(self) -> None:
        self.node: ApexStateNode | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> ApexStateNode:
        if not rclpy.ok():
            rclpy.init()
        self.node = ApexStateNode()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self.node

    def stop(self) -> None:
        if rclpy.ok():
            rclpy.shutdown()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self.node is not None:
            self.node.destroy_node()
            self.node = None

    def _spin(self) -> None:
        if self.node is None:
            return
        try:
            rclpy.spin(self.node)
        except ExternalShutdownException:
            return


def _response_error_code(response: Any) -> int | None:
    value = getattr(response, "error_code", None)
    return _to_int(value)


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_response_success(response: Any) -> bool:
    if bool(getattr(response, "success", False)):
        return True
    error_code = _response_error_code(response)
    return error_code == 0


def _int_response_error(response: Any) -> dict[str, Any]:
    error_code = _response_error_code(response)
    message = str(getattr(response, "message", "") or "")
    error = f"Service returned error_code={error_code}"
    if message:
        error = f"{error}: {message}"
    return {"success": False, "error": error, "error_code": error_code, "message": message}
