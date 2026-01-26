"""
API routes for managing FCP and HCT skeletons.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from BackEnd.db import fcp_skeletons_collection, hct_skeletons_collection, client, DB_NAME
from pathlib import Path
import os

router = APIRouter()

STATIC_DIR = Path(__file__).resolve().parents[2] / "FrontEnd" / "static"


def get_staging_collection(collection_name: str):
    """
    Get collection from gob-staging database for safe testing.
    All skeleton builders save to staging first, then can be migrated to production.
    
    Args:
        collection_name: Name of the collection (e.g., "fcp_skeletons", "hct_skeletons", "plays")
        
    Returns:
        Collection from gob-staging database
    """
    if not client:
        raise HTTPException(status_code=500, detail="MongoDB client not available")
    
    staging_db = client["gob-staging"]
    return staging_db[collection_name]


@router.get("/fcp-skeletons.html")
def serve_fcp_skeletons_builder():
    """Serve the FCP Skeleton Builder HTML page."""
    return FileResponse(STATIC_DIR / "fcp-skeletons.html")


@router.get("/hct-skeletons.html")
def serve_hct_skeletons_builder():
    """Serve the HCT Skeleton Builder HTML page."""
    return FileResponse(STATIC_DIR / "hct-skeletons.html")


class SkeletonCreate(BaseModel):
    variants: Dict[str, Any]
    name: Optional[str] = None


@router.post("/api/fcp-skeletons")
async def create_fcp_skeleton(skeleton_data: SkeletonCreate):
    """
    Create or update an FCP skeleton in MongoDB.
    
    ✅ SAFETY: Always saves to gob-staging database for testing before production migration.
    
    DEVELOPMENT MODE: If a skeleton with the same name exists, it will be overwritten.
    This allows iterating on skeletons during development.
    
    Args:
        skeleton_data: FCP skeleton data from builder
        
    Returns:
        dict: Created/updated skeleton document with _id
    """
    # Always use staging collection for safety
    staging_collection = get_staging_collection("fcp_skeletons")
    
    # Convert to dict
    skeleton_dict = skeleton_data.dict(exclude_none=True)
    
    # Ensure name is provided
    if not skeleton_dict.get("name"):
        raise HTTPException(status_code=400, detail="Skeleton name is required")
    
    # UPSERT: Update if exists (by name), insert if new
    # This allows overwriting skeletons during development
    result = staging_collection.update_one(
        {"name": skeleton_dict["name"]},  # Find by name
        {"$set": skeleton_dict},           # Update all fields
        upsert=True                        # Insert if doesn't exist
    )
    
    # Get the document (either newly inserted or existing one)
    saved_skeleton = staging_collection.find_one({"name": skeleton_dict["name"]})
    saved_skeleton["_id"] = str(saved_skeleton["_id"])
    
    action = "updated" if result.matched_count > 0 else "created"
    
    return {
        "message": f"FCP skeleton {action} successfully to gob-staging",
        "skeleton": saved_skeleton,
        "was_update": result.matched_count > 0
    }


@router.get("/api/fcp-skeletons")
async def get_all_fcp_skeletons():
    """
    Get all FCP skeletons from MongoDB.
    
    ✅ Returns skeletons from gob-staging (where builders save).
    
    Returns:
        dict: List of all FCP skeletons
    """
    try:
        staging_collection = get_staging_collection("fcp_skeletons")
        skeletons = list(staging_collection.find({}))
        for skeleton in skeletons:
            skeleton["_id"] = str(skeleton["_id"])
        
        return {
            "skeletons": skeletons,
            "count": len(skeletons)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching FCP skeletons: {str(e)}")


@router.post("/api/hct-skeletons")
async def create_hct_skeleton(skeleton_data: SkeletonCreate):
    """
    Create or update an HCT skeleton in MongoDB.
    
    ✅ SAFETY: Always saves to gob-staging database for testing before production migration.
    
    DEVELOPMENT MODE: If a skeleton with the same name exists, it will be overwritten.
    This allows iterating on skeletons during development.
    
    Args:
        skeleton_data: HCT skeleton data from builder
        
    Returns:
        dict: Created/updated skeleton document with _id
    """
    # Always use staging collection for safety
    staging_collection = get_staging_collection("hct_skeletons")
    
    # Convert to dict
    skeleton_dict = skeleton_data.dict(exclude_none=True)
    
    # Ensure name is provided
    if not skeleton_dict.get("name"):
        raise HTTPException(status_code=400, detail="Skeleton name is required")
    
    # UPSERT: Update if exists (by name), insert if new
    # This allows overwriting skeletons during development
    result = staging_collection.update_one(
        {"name": skeleton_dict["name"]},  # Find by name
        {"$set": skeleton_dict},           # Update all fields
        upsert=True                        # Insert if doesn't exist
    )
    
    # Get the document (either newly inserted or existing one)
    saved_skeleton = staging_collection.find_one({"name": skeleton_dict["name"]})
    saved_skeleton["_id"] = str(saved_skeleton["_id"])
    
    action = "updated" if result.matched_count > 0 else "created"
    
    return {
        "message": f"HCT skeleton {action} successfully to gob-staging",
        "skeleton": saved_skeleton,
        "was_update": result.matched_count > 0
    }


@router.get("/api/hct-skeletons")
async def get_all_hct_skeletons():
    """
    Get all HCT skeletons from MongoDB.
    
    ✅ Returns skeletons from gob-staging (where builders save).
    
    Returns:
        dict: List of all HCT skeletons
    """
    try:
        staging_collection = get_staging_collection("hct_skeletons")
        skeletons = list(staging_collection.find({}))
        for skeleton in skeletons:
            skeleton["_id"] = str(skeleton["_id"])
        
        return {
            "skeletons": skeletons,
            "count": len(skeletons)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching HCT skeletons: {str(e)}")

