from aplink.aplink_messages import *
from typing import Dict, Any

class MissionManager:
    def __init__(self, send_fn, telemetry_queue):
        self.mission_items = []
        self.send_fn = send_fn
        self.telemetry = telemetry_queue
    
    def send_mission(self, message: Dict[str, Any]):
        self.mission_items = message["data"]
        self.send_fn(aplink_waypoints_count().pack(len(self.mission_items)))
    
    def handle_request_waypoint(self, payload):
        request_waypoint = aplink_request_waypoint()
        request_waypoint.unpack(payload)

        mission_item = self.mission_items[request_waypoint.index]

        if mission_item["type"] == "waypoint":
            type = MISSION_ITEM_TYPE.WAYPOINT
        elif mission_item["type"] == "loiter":
            type = MISSION_ITEM_TYPE.LOITER
        elif mission_item["type"] == "land":
            type = MISSION_ITEM_TYPE.LAND
        
        if mission_item["direction"] == "left":
            direction = LOITER_DIRECTION.LEFT
        else:
            direction = LOITER_DIRECTION.RIGHT
        
        self.send_fn(aplink_mission_item().pack(
            type=type,
            lat=int(mission_item["lat"] * 1e7),
            lon=int(mission_item["lon"] * 1e7),
            radius=mission_item["radius"],
            direction=direction,
            final_leg=mission_item["final_leg"],
            glideslope=mission_item["glideslope"],
            runway_heading=mission_item["runway_heading"]
        ))
    
    def handle_waypoints_ack(self, payload):
        waypoints_ack = aplink_waypoints_ack()
        waypoints_ack.unpack(payload)
        print(f"SENDING MISSION RESULT: {waypoints_ack.success}")

        mission_items = self.mission_items.copy()

        self.telemetry.put({
            "type": "mission",
            "data": mission_items
        })
    
    def handle_get_current_mission(self, message):
        if len(self.mission_items) > 0:
            self.telemetry.put({
                "type": "mission",
                "data": self.mission_items
            })