import redis
import uuid
import json

# Redis connection configuration
redis_conn = redis.StrictRedis(host="localhost", port=6379, db=0)

def queue_task(data: dict) -> str:
    """
    Queue a VRP task into Redis with a unique task ID.
    """
    task_id = str(uuid.uuid4())
    redis_conn.rpush("vrp_tasks", json.dumps({"task_id": task_id, "data": data}))
    return task_id
