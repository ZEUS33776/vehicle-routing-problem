# worker.py
import redis
import json
from vrp_solver import solve_cvrp

# Connect to Redis
redis_conn = redis.StrictRedis(host="localhost", port=6379, db=0)

def process_tasks():
    while True:
        # Dequeue a task from Redis
        task = redis_conn.blpop("vrp_tasks", timeout=0)  # Wait indefinitely for a task
        if task:
            task_data = json.loads(task[1])
            task_id = task_data["task_id"]
            data = task_data["data"]

            try:
                # Solve the CVRP
                solution = solve_cvrp(data)

                # Store the result in Redis
                redis_conn.set(f"vrp_result:{task_id}", json.dumps(solution))

            except Exception as e:
                # Store error information in Redis
                redis_conn.set(f"vrp_result:{task_id}", json.dumps({"error": str(e)}))

if __name__ == "__main__":
    process_tasks()
