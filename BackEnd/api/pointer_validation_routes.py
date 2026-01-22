"""
Pointer Validation API Routes
Phase 2: Endpoint to validate pointers from frontend before navigation/API calls
"""

from fastapi import APIRouter, HTTPException, Query
from BackEnd.utils.pointer_validation import validate_pointer
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/validate-pointer")
def validate_pointer_endpoint(
    pointer_type: str = Query(..., description="Type of pointer: game_id, franchise_id, or tournament_id"),
    pointer_value: str = Query(..., description="Value of the pointer to validate")
):
    """
    Validate that a pointer points to an existing document.
    
    This endpoint allows the frontend to validate pointers before making
    API calls or navigating, ensuring we fail loudly when pointers are invalid.
    
    Args:
        pointer_type: Type of pointer ('game_id', 'franchise_id', 'tournament_id')
        pointer_value: Value of the pointer to validate
    
    Returns:
        {"valid": True, "message": "Pointer is valid"}
    
    Raises:
        HTTPException: If pointer is invalid or document not found
    """
    try:
        validate_pointer(pointer_type, pointer_value)
        return {
            "valid": True,
            "message": f"{pointer_type} is valid and points to existing document"
        }
    except HTTPException as e:
        # Re-raise HTTPException (already has proper status code and detail)
        raise
    except Exception as e:
        logger.error(f"❌ [VALIDATE-POINTER] Unexpected error validating {pointer_type}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal error validating {pointer_type}: {str(e)}"
        )

