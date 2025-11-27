from uuid import UUID

import json

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_device, get_current_user, get_db_session
from app.models.entities import Actuator, Command, Device
from app.models.enums import CommandStatus
from app.schemas.command import (
    CommandAckIn,
    CommandCreateIn,
    CommandCreateResponse,
    CommandStatusResponse,
    DeviceCommandOut,
)

router = APIRouter(prefix="/commands", tags=["commands"])


@router.get("", response_model=list[DeviceCommandOut])
async def fetch_pending_commands(
    device=Depends(get_current_device),
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(
        select(Command).where(
            Command.device_id == device.id, Command.status == CommandStatus.PENDING
        )
    )
    commands = result.scalars().all()
    for command in commands:
        command.status = CommandStatus.SENT
    await session.commit()
    return [DeviceCommandOut.model_validate(cmd) for cmd in commands]


@router.post("/ack", response_model=CommandStatusResponse)
async def acknowledge_command(
    payload: CommandAckIn,
    device=Depends(get_current_device),
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(
        select(Command).where(Command.id == payload.command_id, Command.device_id == device.id)
    )
    command = result.scalar_one_or_none()
    if command is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command not found")

    command.status = payload.status
    if payload.feedback:
        command.message = json.dumps(payload.feedback)
    if command.actuator_id:
        actuator = await session.get(Actuator, command.actuator_id)
        if actuator:
            feedback_state = (payload.feedback or {}).get("state")
            actuator.state = feedback_state or command.command.value
            actuator.last_command_at = datetime.now(timezone.utc)
    await session.commit()
    return CommandStatusResponse(id=command.id, status=command.status, message=command.message)


@router.post("/devices/{device_id}", response_model=CommandCreateResponse)
async def issue_command(
    device_id: UUID,
    payload: CommandCreateIn,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(select(Device).where(Device.id == device_id, Device.user_id == user.id))
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    actuator_result = await session.execute(
        select(Actuator).where(Actuator.id == payload.actuator_id, Actuator.device_id == device.id)
    )
    actuator = actuator_result.scalar_one_or_none()
    if actuator is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown actuator")

    command = Command(
        device_id=device.id,
        actuator_id=actuator.id,
        command=payload.command,
        payload=payload.payload,
    )
    session.add(command)
    await session.commit()
    await session.refresh(command)
    return CommandCreateResponse(
        **DeviceCommandOut.model_validate(command).model_dump(),
        status=command.status,
    )
