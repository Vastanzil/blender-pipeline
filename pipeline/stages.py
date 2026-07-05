"""Pipeline stage enum — used by CheckpointManager and Orchestrator."""
from enum import Enum


class Stage(str, Enum):
    VISION_DETECT   = "vision_detect"
    SPATIAL_LAYOUT  = "spatial_layout"
    ASSET_GEN       = "asset_gen"
    POLY_DECIMATE   = "poly_decimate"
    SCENE_ASSEMBLE  = "scene_assemble"
    VALIDATE        = "validate"
    SAVE            = "save"
