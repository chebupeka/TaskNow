from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import WorkerProfile


def calculate_rating_average(current_average: float, current_count: int, score: int) -> tuple[float, int]:
    next_count = current_count + 1
    next_average = ((current_average * current_count) + score) / next_count
    return round(next_average, 2), next_count


async def apply_worker_review(session: AsyncSession, worker_id: UUID, score: int) -> WorkerProfile:
    profile = await session.get(WorkerProfile, worker_id)
    if profile is None:
        raise ValueError("worker profile not found")

    profile.rating_avg, profile.rating_count = calculate_rating_average(
        profile.rating_avg,
        profile.rating_count,
        score,
    )
    profile.completed_orders += 1
    return profile
