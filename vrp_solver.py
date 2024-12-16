from ortools.constraint_solver import pywrapcp, routing_enums_pb2

def create_data_model(dist_matrix, req_data):
    """
    Prepare the data model required by the OR-Tools solver.
    """
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
    """
    Solve the Capacitated Vehicle Routing Problem (CVRP) using OR-Tools.
    """
    manager = pywrapcp.RoutingIndexManager(
        len(data["distance_matrix"]), data["num_vehicles"], data["starts"], data["ends"]
    )
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        """
        Return the distance between two nodes.
        """
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data["distance_matrix"][from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    def demand_callback(from_index):
        """
        Return the demand at a node.
        """
        from_node = manager.IndexToNode(from_index)
        return data["demands"][from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index, 0, data["vehicle_capacities"], True, "Capacity"
    )
    routing.AddDimension(
        transit_callback_index, 0, max(data["vehicle_max_distances"]), True, "Distance"
    )

    for request in data["pickups_deliveries"]:
        pickup_index = manager.NodeToIndex(request[0])
        delivery_index = manager.NodeToIndex(request[1])
        routing.AddPickupAndDelivery(pickup_index, delivery_index)
        routing.solver().Add(
            routing.VehicleVar(pickup_index) == routing.VehicleVar(delivery_index)
        )

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    )
    solution = routing.SolveWithParameters(search_parameters)

    if not solution:
        return {"error": "No solution found."}

    return format_solution(data, manager, routing, solution)

def format_solution(data, manager, routing, solution):
    """
    Format the solution into a readable structure.
    """
    result = {"routes": [], "objective": solution.ObjectiveValue()}
    total_distance = 0

    for vehicle_id in range(data["num_vehicles"]):
        index = routing.Start(vehicle_id)
        route = []
        route_distance = 0

        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route.append(node_index)
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            route_distance += routing.GetArcCostForVehicle(previous_index, index, vehicle_id)

        result["routes"].append({"vehicle_id": vehicle_id, "route": route, "distance": route_distance})
        total_distance += route_distance

    result["total_distance"] = total_distance
    return result
