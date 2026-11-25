# CMake generated Testfile for 
# Source directory: /home/nvidia/luna-test-runs/20261124-gripper-release-fix/source/verify
# Build directory: /home/nvidia/luna-test-runs/20261124-gripper-release-fix/test-build
# 
# This file includes the relevant testing commands required for 
# testing this directory and lists subdirectories to be tested as well.
add_test(protocol "/home/nvidia/luna-test-runs/20261124-gripper-release-fix/test-build/protocol_test")
set_tests_properties(protocol PROPERTIES  _BACKTRACE_TRIPLES "/home/nvidia/luna-test-runs/20261124-gripper-release-fix/source/verify/CMakeLists.txt;19;add_test;/home/nvidia/luna-test-runs/20261124-gripper-release-fix/source/verify/CMakeLists.txt;0;")
add_test(manual "/home/nvidia/luna-test-runs/20261124-gripper-release-fix/test-build/manual_test")
set_tests_properties(manual PROPERTIES  _BACKTRACE_TRIPLES "/home/nvidia/luna-test-runs/20261124-gripper-release-fix/source/verify/CMakeLists.txt;22;add_test;/home/nvidia/luna-test-runs/20261124-gripper-release-fix/source/verify/CMakeLists.txt;0;")
add_test(ros_adapter "/home/nvidia/luna-test-runs/20261124-gripper-release-fix/test-build/ros_adapter_test")
set_tests_properties(ros_adapter PROPERTIES  ENVIRONMENT "ROS_DOMAIN_ID=93;ROS_LOCALHOST_ONLY=1" TIMEOUT "150" _BACKTRACE_TRIPLES "/home/nvidia/luna-test-runs/20261124-gripper-release-fix/source/verify/CMakeLists.txt;52;add_test;/home/nvidia/luna-test-runs/20261124-gripper-release-fix/source/verify/CMakeLists.txt;0;")
add_test(trigger_without_position "/home/nvidia/luna-test-runs/20261124-gripper-release-fix/test-build/ros_adapter_test" "--no-position")
set_tests_properties(trigger_without_position PROPERTIES  ENVIRONMENT "ROS_DOMAIN_ID=93;ROS_LOCALHOST_ONLY=1" TIMEOUT "150" _BACKTRACE_TRIPLES "/home/nvidia/luna-test-runs/20261124-gripper-release-fix/source/verify/CMakeLists.txt;53;add_test;/home/nvidia/luna-test-runs/20261124-gripper-release-fix/source/verify/CMakeLists.txt;0;")
add_test(wrist_recovery "/home/nvidia/luna-test-runs/20261124-gripper-release-fix/test-build/ros_adapter_test" "--recovery")
set_tests_properties(wrist_recovery PROPERTIES  ENVIRONMENT "ROS_DOMAIN_ID=93;ROS_LOCALHOST_ONLY=1" TIMEOUT "150" _BACKTRACE_TRIPLES "/home/nvidia/luna-test-runs/20261124-gripper-release-fix/source/verify/CMakeLists.txt;54;add_test;/home/nvidia/luna-test-runs/20261124-gripper-release-fix/source/verify/CMakeLists.txt;0;")
add_test(release_reliability "/home/nvidia/luna-test-runs/20261124-gripper-release-fix/test-build/ros_adapter_test" "--release-reliability")
set_tests_properties(release_reliability PROPERTIES  ENVIRONMENT "ROS_DOMAIN_ID=93;ROS_LOCALHOST_ONLY=1" TIMEOUT "150" _BACKTRACE_TRIPLES "/home/nvidia/luna-test-runs/20261124-gripper-release-fix/source/verify/CMakeLists.txt;55;add_test;/home/nvidia/luna-test-runs/20261124-gripper-release-fix/source/verify/CMakeLists.txt;0;")
