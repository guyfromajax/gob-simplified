"""
API routes for managing FCP and HCT skeletons.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from BackEnd.db import fcp_skeletons_collection, hct_skeletons_collection
from bson import ObjectId
from pathlib import Path

router = APIRouter()

STATIC_DIR = Path(__file__).resolve().parents[2] / "FrontEnd" / "static"


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
    _id: Optional[str] = None


@router.post("/api/fcp-skeletons")
async def create_fcp_skeleton(skeleton_data: SkeletonCreate):
    """
    Create or update an FCP skeleton in MongoDB.
    
    Args:
        skeleton_data: FCP skeleton data from builder
        
    Returns:
        dict: Created/updated skeleton document with _id
    """
    skeleton_dict = skeleton_data.dict(exclude_none=True)
    
    # Remove _id from dict if present (will handle separately)
    skeleton_id = skeleton_dict.pop("_id", None)
    
    if skeleton_id:
        # Update existing skeleton
        try:
            result = fcp_skeletons_collection.update_one(
                {"_id": ObjectId(skeleton_id)},
                {"$set": skeleton_dict}
            )
            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="FCP skeleton not found")
            saved_skeleton = fcp_skeletons_collection.find_one({"_id": ObjectId(skeleton_id)})
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error updating skeleton: {str(e)}")
    else:
        # Insert new skeleton
        result = fcp_skeletons_collection.insert_one(skeleton_dict)
        saved_skeleton = fcp_skeletons_collection.find_one({"_id": result.inserted_id})
    
    saved_skeleton["_id"] = str(saved_skeleton["_id"])
    
    action = "updated" if skeleton_id else "created"
    
    return {
        "message": f"FCP skeleton {action} successfully",
        "skeleton": saved_skeleton,
        "was_update": skeleton_id is not None
    }


@router.get("/api/fcp-skeletons")
async def get_all_fcp_skeletons():
    """
    Get all FCP skeletons from MongoDB.
    
    Returns:
        dict: List of all FCP skeletons
    """
    try:
        skeletons = list(fcp_skeletons_collection.find({}))
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
    
    Args:
        skeleton_data: HCT skeleton data from builder
        
    Returns:
        dict: Created/updated skeleton document with _id
    """
    skeleton_dict = skeleton_data.dict(exclude_none=True)
    
    # Remove _id from dict if present (will handle separately)
    skeleton_id = skeleton_dict.pop("_id", None)
    
    if skeleton_id:
        # Update existing skeleton
        try:
            result = hct_skeletons_collection.update_one(
                {"_id": ObjectId(skeleton_id)},
                {"$set": skeleton_dict}
            )
            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="HCT skeleton not found")
            saved_skeleton = hct_skeletons_collection.find_one({"_id": ObjectId(skeleton_id)})
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error updating skeleton: {str(e)}")
    else:
        # Insert new skeleton
        result = hct_skeletons_collection.insert_one(skeleton_dict)
        saved_skeleton = hct_skeletons_collection.find_one({"_id": result.inserted_id})
    
    saved_skeleton["_id"] = str(saved_skeleton["_id"])
    
    action = "updated" if skeleton_id else "created"
    
    return {
        "message": f"HCT skeleton {action} successfully",
        "skeleton": saved_skeleton,
        "was_update": skeleton_id is not None
    }


@router.get("/api/hct-skeletons")
async def get_all_hct_skeletons():
    """
    Get all HCT skeletons from MongoDB.
    
    Returns:
        dict: List of all HCT skeletons
    """
    try:
        skeletons = list(hct_skeletons_collection.find({}))
        for skeleton in skeletons:
            skeleton["_id"] = str(skeleton["_id"])
        
        return {
            "skeletons": skeletons,
            "count": len(skeletons)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching HCT skeletons: {str(e)}")

