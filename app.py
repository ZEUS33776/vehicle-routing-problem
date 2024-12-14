from flask import Flask, request, jsonify, send_from_directory
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import urllib.request
import json
import os
from config import API_KEY 

app = Flask(__name__, static_folder='/home/ubuntu/my-flask-app/swagger-ui/dist')
swagger_ui_dir = '/home/ubuntu/my-flask-app/swagger-ui/dist'

@app.route('/static/swagger.json')
def swagger_json():
    return send_from_directory(app.static_folder, 'swagger.json')

@app.route('/swagger-ui/<path:path>')
def serve_swagger_ui(path):
    return send_from_directory(swagger_ui_dir, path)

@app.route('/swagger')
def swagger_ui():
    return send_from_directory(swagger_ui_dir, 'index.html')

def create_distance_matrix(data):
    coordinates = data["coordinates"]
    API_key = API_KEY
    max_elements = 100
    num_locations = len(coordinates)
    max_rows = max_elements // num_locations
    q, r = divmod(num_locations, max_rows)
    dest_coordinates = coordinates
    distance_matrix = []

    for i in range(q):
        origin_coordinates = coordinates[i * max_rows: (i + 1) * max_rows]
        response = send_request(origin_coordinates, dest_coordinates, API_key)
        distance_matrix += build_distance_matrix(response)

    if r > 0:
        origin_coordinates = coordinates[q * max_rows: q * max_rows + r]
        response = send_request(origin_coordinates, dest_coordinates, API_key)
        distance_matrix += build_distance_matrix(response)

    return distance_matrix

def send_request(origin_coordinates, dest_coordinates, API_key):
    def build_coordinate_str(coordinates):
        return '|'.join(f"{lat},{lng}" for lat, lng in coordinates)

    request_url = 'https://maps.googleapis.com/maps/api/distancematrix/json?units=imperial'
    origin_coordinate_str = build_coordinate_str(origin_coordinates)
    dest_coordinate_str = build_coordinate_str(dest_coordinates)
    request_url += f'&origins={origin_coordinate_str}&destinations={dest_coordinate_str}&key={API_key}'

    with urllib.request.urlopen(request_url) as response:
        json_result = response.read()
    return json.loads(json_result)

def build_distance_matrix(response):
    distance_matrix = []
    for row in response['rows']:
        row_list = [row['elements'][j]['distance']['value'] for j in range(len(row['elements']))]
        distance_matrix.append(row_list)
    return distance_matrix

def create_data_model(dist_matrix, req_data):
    return {
        "distance_matrix": dist_matrix,
        "demands": req_data["demands"],
        "vehicle_capacities": req_data["vehicle_capacities"],
        "vehicle_max_distances": req_data["vehicle_max_distances"],
        "pickups_deliveries": req_data["pickups_deliveries"],
        "num_vehicles": req_data["num_vehicles"],
        "depot": req_data["depot"],
        "starts": req_data["starts"],
        "ends": req_data["ends"]
    }

def solve_cvrp(data):
    manager = pywrapcp.RoutingIndexManager(
        len(data["distance_matrix"]), data["num_vehicles"], data["starts"], data["ends"]
    )

    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data["distance_matrix"][from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return data["demands"][from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)

    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,
        data["vehicle_capacities"],
        True,
        "Capacity",
    )

    routing.AddDimension(
        transit_callback_index,
        0,
        max(data["vehicle_max_distances"]),
        True,
        "Distance",
    )

    distance_dimension = routing.GetDimensionOrDie("Distance")

    for i, max_distance in enumerate(data["vehicle_max_distances"]):
        distance_dimension.CumulVar(routing.End(i)).SetMax(max_distance)

    for request in data["pickups_deliveries"]:
        pickup_index = manager.NodeToIndex(request[0])
        delivery_index = manager.NodeToIndex(request[1])
        routing.AddPickupAndDelivery(pickup_index, delivery_index)
        routing.solver().Add(
            routing.VehicleVar(pickup_index) == routing.VehicleVar(delivery_index)
        )
        routing.solver().Add(
            distance_dimension.CumulVar(pickup_index)
            <= distance_dimension.CumulVar(delivery_index)
        )

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.FromSeconds(30)

    solution = routing.SolveWithParameters(search_parameters)

    return routing, manager, solution

def format_solution(data, manager, routing, solution):
    if not solution:
        return {"error": "No solution found."}
    
    result = {"routes": [], "objective": solution.ObjectiveValue()}
    total_distance = 0

    for vehicle_id in range(data["num_vehicles"]):
        index = routing.Start(vehicle_id)
        route = []
        route_distance = 0
        route_load = 0

        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            action = "Visit"
            if node_index in [req[0] for req in data["pickups_deliveries"]]:
                route_load += data["demands"][node_index]
                action = "Pickup"
            elif node_index in [req[1] for req in data["pickups_deliveries"]]:
                route_load -= data["demands"][node_index]
                action = "Delivery"

            route.append({"node": node_index, "load": route_load, "action": action})
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            route_distance += routing.GetArcCostForVehicle(previous_index, index, vehicle_id)

        route.append({"node": manager.IndexToNode(index), "load": route_load})
        result["routes"].append({"vehicle_id": vehicle_id, "route": route, "distance": route_distance})
        total_distance += route_distance

    result["total_distance"] = total_distance
    return result

@app.route('/solve', methods=['POST'])
def solve_route():
    try:
        req_data = request.get_json()
        coordinates = req_data.get("coordinates")

        if not coordinates:
            return jsonify({"error": "Coordinates not provided"}), 400

        distance_matrix = create_distance_matrix({"coordinates": coordinates})

        data_model = create_data_model(distance_matrix, req_data)

        routing, manager, solution = solve_cvrp(data_model)

        return jsonify(format_solution(data_model, manager, routing, solution))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
