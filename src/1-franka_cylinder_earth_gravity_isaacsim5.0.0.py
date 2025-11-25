from isaacsim import SimulationApp

# Launch the simulator
simulation_app = SimulationApp({"headless": False})

# IMPORTANT: Import Isaac Sim modules AFTER SimulationApp initialization
import numpy as np
import os
from isaacsim.core.api.world import World
from isaacsim.core.api.objects import DynamicCylinder
from isaacsim.robot.manipulators.examples.franka import Franka
from isaacsim.core.utils.types import ArticulationAction
from isaacsim.robot_motion.motion_generation import RmpFlow, ArticulationMotionPolicy
from isaacsim.core.utils.extensions import get_extension_path_from_name
from isaacsim.core.utils.numpy.rotations import euler_angles_to_quats

try:
    import dearpygui.dearpygui as dpg
    IMGUI_AVAILABLE = True
except ImportError:
    IMGUI_AVAILABLE = False
    print("[WARNING] dearpygui not available - control panel disabled")


class FrankaCylinderMoverRMPflow:
    """
    State machine controller using RMPflow for smooth motion planning
    """
    
    def __init__(self, world: World, franka: Franka):
        self.world = world
        self.franka = franka
        self.cylinder = None
        self.rmpflow = None
        self.articulation_rmpflow = None
        
        # Store initial joint positions (will be set after world reset)
        self.initial_joint_positions = np.array([0.0, 0.0, 0.0, -1.57, 0.0, 1.57, 0.785, 0.04, 0.04])
        
        # State machine states
        self.states = [
            "idle",
            "open_gripper",
            "approach_cylinder",
            "lower_to_grasp",
            "close_gripper",
            "lift_cylinder",
            "move_to_target",
            "lower_to_target",
            "open_gripper",
            "retreat_home",
            "done"
        ]
        self.current_state_index = 0
        self.step_counter = 0
        self.steps_per_state = 250
        
        # End effector positions
        self.cylinder_pickup_pos = np.array([0.4, 0.25, 0.05])
        self.cylinder_place_pos = np.array([0.4, -0.25, 0.05])
        self.home_pos = np.array([0.3, 0.0, 0.6])
        self.safe_height = 0.32
        
        # Gripper states
        self.gripper_open = np.array([0.039, 0.039])
        self.gripper_closed = np.array([0.0, 0.0])
        
        # Orientation for end effector (pointing down)
        self.grasp_orientation = euler_angles_to_quats(np.array([0, np.pi, 0]))
        
    def setup_rmpflow(self):
        """Initialize RMPflow controller for smooth IK"""
        print("\nInitializing RMPflow...")
        
        try:
            # Get motion generation extension path
            mg_extension_path = get_extension_path_from_name(
                "isaacsim.robot_motion.motion_generation"
            )
            rmp_config_dir = os.path.join(mg_extension_path, "motion_policy_configs")
            
            # Initialize RMPflow
            self.rmpflow = RmpFlow(
                robot_description_path=os.path.join(
                    rmp_config_dir, "franka/rmpflow/robot_descriptor.yaml"
                ),
                urdf_path=os.path.join(
                    rmp_config_dir, "franka/lula_franka_gen.urdf"
                ),
                rmpflow_config_path=os.path.join(
                    rmp_config_dir, "franka/rmpflow/franka_rmpflow_common.yaml"
                ),
                end_effector_frame_name="right_gripper",
                maximum_substep_size=0.00334
            )
            
            # Create motion policy wrapper
            self.articulation_rmpflow = ArticulationMotionPolicy(
                self.franka, self.rmpflow
            )
            
            print("? RMPflow initialized successfully")
            return True
            
        except Exception as e:
            print(f"? Failed to initialize RMPflow: {e}")
            print("  Make sure isaacsim.robot_motion.motion_generation extension is installed")
            return False
    
    def setup_scene(self):
        """Setup the scene with robot and cylinder"""
        print("\n" + "="*60)
        print("Setting up scene...")
        print("="*60)
        
        # Add ground plane
        self.world.scene.add_default_ground_plane()
        
        # Add cylinder on the left side
        self.cylinder = self.world.scene.add(
            DynamicCylinder(
                prim_path="/World/Cylinder",
                name="target_cylinder",
                position=self.cylinder_pickup_pos,
                orientation=np.array([1.0, 0.0, 0.0, 0.0]),
                radius=0.036,
                height=0.08,
                color=np.array([0.0, 0.5, 1.0]),
                mass=0.05
            )
        )
        
        print("? Scene setup complete")
        print(f"  - Franka robot at origin")
        print(f"  - Cylinder at left: {self.cylinder_pickup_pos}")
        print(f"  - Target position (right): {self.cylinder_place_pos}")
        print(f"  - Camera positioned to the right, viewing robot center")
    
    def capture_initial_positions(self):
        """Capture initial joint positions after world is properly initialized"""
        try:
            positions = self.franka.get_joint_positions()
            if positions is not None:
                self.initial_joint_positions = positions.copy()
                print(f"? Initial joint positions captured: {len(positions)} joints")
                return True
        except Exception as e:
            print(f"[WARNING] Could not capture initial positions: {e}")
        return False
    
    def reset_controller_state(self):
        """Reset only the controller state without affecting physics"""
        self.current_state_index = 0
        self.step_counter = 0
        print("? Controller state reset")
    
    def reset_scene(self):
        """Reset the scene to initial state"""
        print("\nResetting scene...")
        
        try:
            # Reset cylinder position
            if self.cylinder is not None:
                self.cylinder.set_world_pose(
                    position=self.cylinder_pickup_pos,
                    orientation=np.array([1.0, 0.0, 0.0, 0.0])
                )
                # Set velocity to zero
                self.cylinder.set_linear_velocity(np.array([0.0, 0.0, 0.0]))
                self.cylinder.set_angular_velocity(np.array([0.0, 0.0, 0.0]))
            
            # Reset robot to initial position
            if self.franka is not None and self.initial_joint_positions is not None:
                self.franka.set_joint_positions(self.initial_joint_positions.copy())
                # Get number of joints and set velocities to zero
                num_joints = len(self.initial_joint_positions)
                self.franka.set_joint_velocities(np.zeros(num_joints))
            
            print("? Scene reset complete")
        except Exception as e:
            print(f"[WARNING] Error during scene reset: {e}")
        
    def get_current_state(self):
        """Get current state name"""
        if self.current_state_index < len(self.states):
            return self.states[self.current_state_index]
        return "done"
    
    def move_to_next_state(self):
        """Transition to next state"""
        self.current_state_index += 1
        self.step_counter = 0
        state = self.get_current_state()
        if state != "done":
            print(f"\n? {state.upper()}")
    
    def set_end_effector_target(self, position, open_gripper=True):
        """Set RMPflow target for smooth motion"""
        # Set target position and orientation
        self.rmpflow.set_end_effector_target(
            position,
            self.grasp_orientation
        )
        
        # Handle gripper
        current_positions = self.franka.get_joint_positions()
        if current_positions is not None:
            if open_gripper:
                current_positions[-2:] = self.gripper_open
            else:
                current_positions[-2:] = self.gripper_closed
        
        return current_positions
    
    def control_loop(self, dt: float):
        """Main control loop"""
        state = self.get_current_state()
        
        if state == "done":
            return True
        
        try:
            # Get current robot state
            current_positions = self.franka.get_joint_positions()
            if current_positions is None:
                return False
            
            # State machine logic
            if state == "idle":
                if self.step_counter > 50:
                    self.move_to_next_state()
            
            elif state == "approach_cylinder":
                target_pos = self.cylinder_pickup_pos.copy()
                target_pos[2] += 0.15
                self.set_end_effector_target(target_pos, open_gripper=True)
                action = self.articulation_rmpflow.get_next_articulation_action(dt)
                self.franka.apply_action(action)
                if self.step_counter > self.steps_per_state:
                    self.move_to_next_state()
            
            elif state == "lower_to_grasp":
                self.set_end_effector_target(self.cylinder_pickup_pos, open_gripper=True)
                action = self.articulation_rmpflow.get_next_articulation_action(dt)
                self.franka.apply_action(action)
                if self.step_counter > self.steps_per_state:
                    self.move_to_next_state()
            
            elif state == "close_gripper":
                current_positions = self.franka.get_joint_positions()
                current_positions[-2:] = self.gripper_closed
                action = ArticulationAction(joint_positions=current_positions)
                self.franka.apply_action(action)
                if self.step_counter > self.steps_per_state:
                    self.move_to_next_state()
            
            elif state == "lift_cylinder":
                lift_pos = self.cylinder_pickup_pos.copy()
                lift_pos[2] = self.safe_height
                self.set_end_effector_target(lift_pos, open_gripper=False)
                action = self.articulation_rmpflow.get_next_articulation_action(dt)
                self.franka.apply_action(action)
                if self.step_counter > self.steps_per_state:
                    self.move_to_next_state()
            
            elif state == "move_to_target":
                move_pos = self.cylinder_place_pos.copy()
                move_pos[2] = self.safe_height
                self.set_end_effector_target(move_pos, open_gripper=False)
                action = self.articulation_rmpflow.get_next_articulation_action(dt)
                self.franka.apply_action(action)
                if self.step_counter > self.steps_per_state:
                    self.move_to_next_state()
            
            elif state == "lower_to_target":
                self.set_end_effector_target(self.cylinder_place_pos, open_gripper=False)
                action = self.articulation_rmpflow.get_next_articulation_action(dt)
                self.franka.apply_action(action)
                if self.step_counter > self.steps_per_state:
                    self.move_to_next_state()
            
            elif state == "open_gripper":
                current_positions = self.franka.get_joint_positions()
                current_positions[-2:] = self.gripper_open
                action = ArticulationAction(joint_positions=current_positions)
                self.franka.apply_action(action)
                if self.step_counter > self.steps_per_state:
                    self.move_to_next_state()
            
            elif state == "retreat_home":
                self.set_end_effector_target(self.home_pos, open_gripper=True)
                action = self.articulation_rmpflow.get_next_articulation_action(dt)
                self.franka.apply_action(action)
                if self.step_counter > self.steps_per_state:
                    self.move_to_next_state()
            
            self.step_counter += 1
            
        except Exception as e:
            print(f"[WARNING] Control loop error: {e}")
            pass
        
        return False


class SimulationController:
    """Manages simulation state and control panel"""
    
    def __init__(self, world: World, controller: FrankaCylinderMoverRMPflow):
        self.world = world
        self.controller = controller
        self.is_running = False
        self.is_task_complete = False
        self.frame_count = 0
        self.gui_ready = False
        self.exit_requested = False
        self.last_gui_update = 0
        self.gui_update_interval = 5
        
        # Restart state machine
        self.restart_requested = False
        self.restart_steps_remaining = 0
        
    def setup_gui(self):
        """Setup DearPyGUI control panel"""
        if not IMGUI_AVAILABLE:
            return
        
        try:
            dpg.create_context()
            
            with dpg.window(label="Franka Simulation Control", tag="main_window", 
                            width=400, height=380, pos=(50, 50), no_close=True):
                dpg.add_text("Franka Cylinder Mover - RMPflow", color=(100, 200, 255))
                dpg.add_text("? EARTH GRAVITY: 9.81 m/s²", color=(255, 200, 100))
                dpg.add_separator()
                
                # Status
                dpg.add_text("Status:", color=(200, 200, 200))
                dpg.add_text("STOPPED", tag="status_text", color=(255, 100, 100))
                
                # State info
                dpg.add_text("Current State:", color=(200, 200, 200))
                dpg.add_text("idle", tag="state_text", color=(255, 200, 100))
                
                # Frame counter
                dpg.add_text("Frames: 0", tag="frame_text", color=(150, 150, 150))
                
                dpg.add_separator()
                
                # Control buttons
                dpg.add_button(label="START", callback=self.start_simulation, 
                              width=380, height=40, tag="start_button")
                
                dpg.add_button(label="STOP", callback=self.stop_simulation, 
                              width=380, height=40, tag="stop_button")
                
                dpg.add_button(label="RESET", callback=self.request_restart, 
                              width=380, height=40, tag="restart_button")
                
                dpg.add_separator()
                
                dpg.add_button(label="EXIT", callback=self.exit_simulation, 
                              width=380, height=40, tag="exit_button")
            
            dpg.create_viewport(title="Franka Control Panel", width=420, height=430, vsync=False)
            dpg.setup_dearpygui()
            dpg.show_viewport()
            dpg.set_primary_window("main_window", True)
            
            self.gui_ready = True
            print("? Control panel initialized")
            return True
        except Exception as e:
            print(f"[WARNING] GUI setup error: {e}")
            self.gui_ready = False
            return False
    
    def update_gui(self):
        """Update GUI elements each frame"""
        if not self.gui_ready or not IMGUI_AVAILABLE:
            return
        
        # Only update GUI every N frames to reduce overhead
        self.last_gui_update += 1
        if self.last_gui_update < self.gui_update_interval:
            return
        
        self.last_gui_update = 0
        
        try:
            # Update status
            if self.restart_requested:
                status = "RESETTING..."
                status_color = (200, 150, 100)
            elif self.is_task_complete:
                status = "COMPLETED"
                status_color = (255, 255, 100)
            elif self.is_running:
                status = "PLAYING"
                status_color = (100, 255, 100)
            else:
                status = "STOPPED"
                status_color = (255, 100, 100)
            
            dpg.set_value("status_text", status)
            dpg.configure_item("status_text", color=status_color)
            
            # Update state
            state = self.controller.get_current_state()
            dpg.set_value("state_text", state)
            
            # Update frame counter
            dpg.set_value("frame_text", f"Frames: {self.frame_count}")
            
            # Enable/disable buttons based on state
            if self.restart_requested:
                dpg.configure_item("start_button", enabled=False)
                dpg.configure_item("stop_button", enabled=False)
                dpg.configure_item("restart_button", enabled=False)
            elif self.is_running:
                dpg.configure_item("start_button", enabled=False)
                dpg.configure_item("stop_button", enabled=True)
                dpg.configure_item("restart_button", enabled=True)
            else:
                dpg.configure_item("start_button", enabled=True)
                dpg.configure_item("stop_button", enabled=False)
                dpg.configure_item("restart_button", enabled=True)
            
            # Process GUI events
            if dpg.is_dearpygui_running():
                dpg.render_dearpygui_frame()
        except Exception as e:
            print(f"[WARNING] GUI update error: {e}")
    
    def start_simulation(self):
        """Start the simulation"""
        try:
            if not self.is_running and not self.restart_requested:
                print("\n? Simulation STARTED")
                
                # If task was complete, reset it first
                if self.is_task_complete:
                    self.controller.reset_controller_state()
                    self.is_task_complete = False
                
                self.is_running = True
                
                # Ensure world is playing
                if not self.world.is_playing():
                    self.world.play()
        except Exception as e:
            print(f"[ERROR] Start failed: {e}")
    
    def stop_simulation(self):
        """Stop the simulation"""
        try:
            if self.is_running:
                self.is_running = False
                print("\n? Simulation STOPPED")
                self.restart_requested = False
        except Exception as e:
            print(f"[ERROR] Stop failed: {e}")
    
    def request_restart(self):
        """Request reset/restart - will be processed in main loop to avoid blocking"""
        if not self.restart_requested:
            print("\n? Reset requested (will process in next frames)...")
            
            # If simulation is running, stop it
            if self.is_running:
                self.is_running = False
                print("  Stopping simulation...")
            
            self.restart_requested = True
            self.restart_steps_remaining = 20  # Process over next 20 frames
    
    def process_restart(self):
        """Process restart operation across multiple frames"""
        if not self.restart_requested:
            return
        
        self.restart_steps_remaining -= 1
        
        if self.restart_steps_remaining == 20:
            # Step 1: Stop and reset controller state
            self.is_running = False
            self.is_task_complete = False
            self.controller.reset_controller_state()
            print("  [1/5] Stopped execution and reset controller state")
        
        elif self.restart_steps_remaining == 15:
            # Step 2: Reset scene
            self.controller.reset_scene()
            print("  [2/5] Reset scene")
        
        elif self.restart_steps_remaining == 10:
            # Step 3: Let world step a few times to settle
            for _ in range(5):
                self.world.step(render=False)
            print("  [3/5] Physics settled")
        
        elif self.restart_steps_remaining == 5:
            # Step 4: Reset world
            try:
                self.world.reset()
                self.controller.capture_initial_positions()
                print("  [4/5] World reset")
            except Exception as e:
                print(f"  [WARNING] World reset error: {e}")
        
        elif self.restart_steps_remaining == 1:
            # Step 5: Complete restart
            self.frame_count = 0
            self.restart_requested = False
            print("  [5/5] Simulation state reset to initial")
            print("? Reset complete - simulation is STOPPED and ready to START")
    
    def exit_simulation(self):
        """Exit the simulation"""
        print("\n? Exit requested...")
        self.exit_requested = True


def setup_camera(world: World):
    """Setup camera positioned to the right of robot, viewing robot center while seeing entire robot"""
    try:
        from isaacsim.core.utils.viewports import set_camera_view
        
        # Camera position: to the right (increased X), further back (more negative Y), elevated (Z)
        # This gives a better 3/4 view showing the entire robot
        camera_position = np.array([1.75, -0.4, 0.7])   # More to the right and back, elevated
        camera_target = np.array([0.0, 0.0, 0.3])      # Looking at robot center
        
        set_camera_view(eye=camera_position, target=camera_target)
        print("? Camera positioned: right side view, showing entire robot")
        return True
    except Exception as e:
        print(f"[WARNING] Could not set camera view: {e}")
        # Try alternative method
        try:
            viewport = world.get_viewport()
            if viewport is not None:
                # Position camera
                viewport.set_camera_position(np.array([0.7, -0.6, 0.5]))
                viewport.set_camera_target(np.array([0.0, 0.0, 0.3]))
                print("? Camera positioned using viewport method: right side view")
                return True
        except Exception as e2:
            print(f"[WARNING] Alternative camera setup failed: {e2}")
        return False


def set_earth_gravity(world: World):
    """Configure Earth gravity (9.81 m/s²)"""
    try:
        # Method 1: Using PhysicsContext (Isaac Sim 5.0.0)
        from isaacsim.core.utils.physics import get_physics_scene
        
        physics_scene = get_physics_scene()
        if physics_scene is not None:
            # Set Earth gravity vector (negative Z direction)
            physics_scene.set_gravity(np.array([0.0, 0.0, -9.81]))
            print("? Earth gravity set: 9.81 m/s² (Method 1: PhysicsContext)")
            return True
    except Exception as e:
        print(f"[INFO] Method 1 failed: {e}")
    
    try:
        # Method 2: Direct stage manipulation
        from pxr import UsdPhysics, PhysicsSchemaTools
        
        stage = world.stage
        # Get or create physics scene
        physics_scene_path = "/physicsScene"
        physics_scene = UsdPhysics.Scene.Get(stage, physics_scene_path)
        
        if not physics_scene:
            physics_scene = UsdPhysics.Scene.Define(stage, physics_scene_path)
        
        # Set gravity
        gravity_attr = physics_scene.GetGravityDirectionAttr()
        gravity_mag_attr = physics_scene.GetGravityMagnitudeAttr()
        
        gravity_attr.Set((0.0, 0.0, -1.0))  # Direction (down)
        gravity_mag_attr.Set(9.81)         # Magnitude (m/s²)
        
        print("? Earth gravity set: 9.81 m/s² (Method 2: USD Stage)")
        return True
    except Exception as e:
        print(f"[INFO] Method 2 failed: {e}")
    
    try:
        # Method 3: Using World API
        world.get_physics_context().set_gravity(-9.81)
        print("? Earth gravity set: 9.81 m/s² (Method 3: World API)")
        return True
    except Exception as e:
        print(f"[WARNING] All gravity setup methods failed: {e}")
        print("  Using default Earth gravity (9.811 m/s²)")
        return False


def main():
    """Main function"""
    print("\n" + "="*60)
    print("FRANKA CYLINDER MOVER WITH RMPFLOW")
    print("? EARTH GRAVITY SIMULATION: 9.81 m/s²")
    print("Smooth inverse kinematics control")
    print("Isaac Sim 5.0.0")
    print("="*60)
    
    # Create world
    world = World(stage_units_in_meters=1.0)
    
    # Set Earth gravity BEFORE adding objects
    print("\nConfiguring Earth gravity...")
    set_earth_gravity(world)
    
    # Add Franka robot
    print("\nAdding Franka robot...")
    franka = world.scene.add(
        Franka(
            prim_path="/World/Franka",
            name="franka_robot",
            position=np.array([0.0, 0.0, 0.0])
        )
    )
    
    # Create controller
    controller = FrankaCylinderMoverRMPflow(world, franka)
    
    # Setup scene
    controller.setup_scene()
    
    # Initialize world
    print("\nInitializing simulation...")
    try:
        world.reset()
        
        # Re-apply gravity after reset (sometimes reset can override settings)
        set_earth_gravity(world)
        
    except Exception as e:
        print(f"[ERROR] Failed to reset world: {e}")
        simulation_app.close()
        return
    
    # Setup camera
    print("\nSetting up camera...")
    setup_camera(world)
    
    # Capture initial positions after world is ready
    print("Capturing initial joint positions...")
    controller.capture_initial_positions()
    
    # Setup RMPflow
    if not controller.setup_rmpflow():
        print("[ERROR] RMPflow setup failed")
        simulation_app.close()
        return
    
    # Create simulation controller
    sim_controller = SimulationController(world, controller)
    
    # Setup GUI
    if IMGUI_AVAILABLE:
        sim_controller.setup_gui()
    else:
        print("[WARNING] dearpygui not available - running without control panel\n")
    
    print("\n" + "="*60)
    print("SIMULATION READY")
    print("? Earth Gravity: 9.81 m/s²")
    print("="*60)
    print("\nUse the control panel to START the simulation")
    print("="*60 + "\n")
    
    if not IMGUI_AVAILABLE:
        # Auto-start if no GUI
        world.play()
        sim_controller.is_running = True
    
    # Simulation loop
    frame_count = 0
    last_reported_frame = 0
    
    while simulation_app.is_running() and not sim_controller.exit_requested:
        try:
            # Process reset requests first (non-blocking)
            if sim_controller.restart_requested:
                sim_controller.process_restart()
            
            # Update GUI (safe to call always)
            if IMGUI_AVAILABLE:
                sim_controller.update_gui()
            
            # Step simulation
            world.step(render=True)
            
            # Only execute control loop if running
            if sim_controller.is_running and world.is_playing() and not sim_controller.restart_requested:
                # Estimate dt from frame time
                dt_estimate = world.get_physics_dt()
                
                done = controller.control_loop(dt_estimate)
                
                # Print status every 200 frames
                if frame_count - last_reported_frame >= 200:
                    state = controller.get_current_state()
                    if state != "done":
                        print(f"Frame {frame_count:6d} | State: {state}")
                    last_reported_frame = frame_count
                
                frame_count += 1
                sim_controller.frame_count = frame_count
                
                if done and not sim_controller.is_task_complete:
                    print("\n" + "="*60)
                    print("? TASK COMPLETED!")
                    print("Cylinder successfully moved from left to right")
                    print("? Under Earth gravity (9.81 m/s²)")
                    print("="*60)
                    print("\nUse the control panel to RESET, START again, or EXIT")
                    print("")
                    sim_controller.is_task_complete = True
                    sim_controller.stop_simulation()
        
        except KeyboardInterrupt:
            print("\n\n? Interrupted by user")
            break
        except Exception as e:
            print(f"[ERROR] Main loop error: {e}")
            import traceback
            traceback.print_exc()
            break
    
    print("\nClosing simulation...")
    if IMGUI_AVAILABLE and sim_controller.gui_ready:
        try:
            if dpg.is_dearpygui_running():
                dpg.destroy_context()
        except:
            pass
    simulation_app.close()
    print("Goodbye!")


if __name__ == "__main__":
    main()
