cmake_minimum_required(VERSION 3.16)
project(luna_impedance_entry_fix)
set(CMAKE_CXX_STANDARD 17)
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(std_srvs REQUIRED)
find_package(tf2 REQUIRED)
find_package(marvin_msgs REQUIRED)
find_library(GENTO_LIBRARY NAMES GentoSDK REQUIRED)
add_executable(marvin_robot_node src/marvin_robot_node.cpp src/marvin_robot.cpp)
target_compile_definitions(marvin_robot_node PRIVATE CMPL_LIN)
target_include_directories(marvin_robot_node PRIVATE
 /usr/local/include/gentosdk/L1Robot /usr/local/include/gentosdk/Common
 /usr/local/include/gentosdk/L0Control /usr/local/include/gentosdk/Kinematics
 /usr/local/include/gentosdk/Kinematics/ArmKinematics /usr/local/include/gentosdk/Kinematics/BaseMath
 /usr/local/include/gentosdk/Kinematics/DynaIdent /usr/local/include/gentosdk/Kinematics/KineCommon
 /usr/local/include/gentosdk/Kinematics/MotionPlanner /usr/local/include/gentosdk/Kinematics/SkyeBodyKinematics)
target_link_libraries(marvin_robot_node ${GENTO_LIBRARY} pthread rt)
ament_target_dependencies(marvin_robot_node rclcpp sensor_msgs geometry_msgs std_msgs std_srvs tf2 marvin_msgs)
add_executable(test_impedance_entry test_impedance_entry.cpp)
target_compile_options(test_impedance_entry PRIVATE -Wall -Wextra -Werror -UNDEBUG)
enable_testing()
add_test(NAME impedance_entry COMMAND test_impedance_entry)
