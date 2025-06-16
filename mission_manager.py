from aplink.aplink_messages import *
from typing import Dict, Any

class MissionManager:
    def __init__(self, send_fn, telemetry_queue):
        self.send_fn = send_fn
        self.telemetry = telemetry_queue

        self.mission_items = []
        self.mission_type: MISSION_ITEM_TYPE
        self.radius: float
        self.direction: LOITER_DIRECTION
        self.final_leg = 0
        self.glideslope = 0
        self.runway_heading = 0
    
    def send_mission(self, message: Dict[str, Any]):
        self.mission_items = message["data"]

        if message["mission_type"] == "waypoint":
            type = MISSION_ITEM_TYPE.WAYPOINT
        elif message["mission_type"] == "loiter":
            type = MISSION_ITEM_TYPE.LOITER
        elif message["mission_type"] == "land":
            type = MISSION_ITEM_TYPE.LAND
        
        if message["direction"] == "left":
            direction = LOITER_DIRECTION.LEFT
        else:
            direction = LOITER_DIRECTION.RIGHT
        
        self.mission_type = message["mission_type"]
        self.direction = message["direction"]
        self.radius = message["radius"]
        self.final_leg = message["final_leg"]
        self.glideslope = message["glideslope"]
        self.runway_heading = message["runway_heading"]

        print(f"Sent mission direction {self.direction}")

        self.send_fn(aplink_waypoints_count().pack(
            num_waypoints=len(self.mission_items),
            type=type,
            radius=self.radius,
            direction=direction,
            final_leg=self.final_leg,
            glideslope=self.glideslope,
            runway_heading=self.runway_heading
        ))
    
    def handle_request_waypoint(self, payload):
        request_waypoint = aplink_request_waypoint()
        request_waypoint.unpack(payload)

        print(request_waypoint.index)

        mission_item = self.mission_items[request_waypoint.index]
        
        self.send_fn(aplink_mission_item().pack(
            lat=int(mission_item["lat"] * 1e7),
            lon=int(mission_item["lon"] * 1e7)
        ))
    
    def handle_waypoints_ack(self, payload):
        waypoints_ack = aplink_waypoints_ack()
        waypoints_ack.unpack(payload)
        print(f"SENDING MISSION RESULT: {waypoints_ack.success}")

        mission_items = self.mission_items.copy()

        self.telemetry.put({
            "type": "mission",
            "mission_type": self.mission_type,
            "radius": self.radius,
            "direction": self.direction,
            "final_leg": self.final_leg,
            "glideslope": self.glideslope,
            "runway_heading": self.runway_heading,
            "data": mission_items
        })
    
    def handle_get_current_mission(self, message):
        if len(self.mission_items) > 0:
            self.telemetry.put({
                "type": "mission",
                "mission_type": self.mission_type,
                "radius": self.radius,
                "direction": self.direction,
                "final_leg": self.final_leg,
                "glideslope": self.glideslope,
                "runway_heading": self.runway_heading,
                "data": self.mission_items
            })