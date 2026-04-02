import time
import redis.asyncio as aioredis


class Matcher:
    """
    Redis-схема:
      waiting_queue       — ZSET (score = timestamp, для честной очереди)
      session:{user_id}   — STRING (partner_id)
      banned:{user_id}    — STRING (expire = ban duration)
      reports:{user_id}   — SET (reporter_ids)
      users               — SET (все зарегистрированные user_id)
      msg_count:{user_id} — STRING int (счётчик сообщений)
    """

    def __init__(self, redis_url: str):
        self.redis = aioredis.from_url(redis_url, decode_responses=True)

    # ─── Регистрация ──────────────────────────────────────────────────────────

    async def register_user(self, user_id: int):
        await self.redis.sadd("users", user_id)

    # ─── Очередь ──────────────────────────────────────────────────────────────

    async def enqueue(self, user_id: int) -> int | None:
        """
        Добавляет user_id в очередь и пытается найти пару.
        Возвращает partner_id если нашёл, иначе None.
        """
        # Убираем себя из очереди на случай повторного нажатия
        await self.redis.zrem("waiting_queue", user_id)

        # Ищем первого в очереди (кроме себя)
        candidates = await self.redis.zrange("waiting_queue", 0, -1)
        for candidate in candidates:
            cid = int(candidate)
            if cid != user_id:
                # Нашли — забираем из очереди
                removed = await self.redis.zrem("waiting_queue", candidate)
                if removed:  # защита от race condition
                    return cid

        # Никого нет — добавляем себя в очередь
        await self.redis.zadd("waiting_queue", {str(user_id): time.time()})
        return None

    async def dequeue(self, user_id: int):
        """Убрать из очереди ожидания."""
        await self.redis.zrem("waiting_queue", user_id)

    async def is_in_queue(self, user_id: int) -> bool:
        score = await self.redis.zscore("waiting_queue", user_id)
        return score is not None

    # ─── Сессии ───────────────────────────────────────────────────────────────

    async def create_session(self, user_a: int, user_b: int):
        pipe = self.redis.pipeline()
        pipe.set(f"session:{user_a}", user_b)
        pipe.set(f"session:{user_b}", user_a)
        await pipe.execute()

    async def get_partner(self, user_id: int) -> int | None:
        val = await self.redis.get(f"session:{user_id}")
        return int(val) if val else None

    async def end_session(self, user_id: int):
        """Завершает сессию для обоих участников."""
        partner_id = await self.get_partner(user_id)
        pipe = self.redis.pipeline()
        pipe.delete(f"session:{user_id}")
        if partner_id:
            pipe.delete(f"session:{partner_id}")
        # Убираем из очереди на всякий случай
        pipe.zrem("waiting_queue", user_id)
        await pipe.execute()

    # ─── Баны и жалобы ────────────────────────────────────────────────────────

    async def is_banned(self, user_id: int) -> bool:
        return await self.redis.exists(f"banned:{user_id}") > 0

    async def ban_user(self, user_id: int, hours: int = 24):
        """Банит пользователя на N часов."""
        await self.redis.setex(f"banned:{user_id}", hours * 3600, "1")
        # Выкидываем из очереди и сессии
        await self.dequeue(user_id)
        await self.end_session(user_id)

    async def add_report(self, reported_id: int, reporter_id: int) -> int:
        """
        Добавляет жалобу. Возвращает общее количество жалоб за последние 7 дней.
        Использует SET чтобы один человек не мог пожаловаться дважды.
        """
        key = f"reports:{reported_id}"
        await self.redis.sadd(key, reporter_id)
        await self.redis.expire(key, 7 * 24 * 3600)  # TTL 7 дней
        count = await self.redis.scard(key)
        return count

    # ─── Статистика ───────────────────────────────────────────────────────────

    async def increment_message_count(self, user_id: int):
        key = f"msg_count:{user_id}"
        await self.redis.incr(key)
        await self.redis.expire(key, 24 * 3600)

    async def get_stats(self) -> dict:
        waiting = await self.redis.zcard("waiting_queue")
        total_users = await self.redis.scard("users")
        # Считаем активные сессии (каждая пара = 2 ключа)
        session_keys = len(await self.redis.keys("session:*"))
        active_sessions = session_keys // 2
        return {
            "waiting": waiting,
            "active_sessions": active_sessions,
            "total_users": total_users,
        }

    async def get_queue_position(self, user_id: int) -> int | None:
        """Позиция в очереди (1-based)."""
        rank = await self.redis.zrank("waiting_queue", user_id)
        return rank + 1 if rank is not None else None
