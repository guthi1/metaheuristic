from typing import List, Tuple
from tqdm import tqdm
from tsptw import TSPTW
from utils.ant import Ant
from copy import deepcopy
from utils.beam_search import ProbabilisticBeamSearch
import time


def solve(tsptw: TSPTW) -> List[int]:
    """Advanced solver for the prize-collecting Steiner tree problem.

    Args:
        tsptw (TSPTW): object containing the graph for the instance to solve

    Returns:
        solution (List[int]): solution in the format [0, p1, p2, ..., pn, 0] where p1, ..., pn is a permutation 
            of the nodes. p1, ..., pn are all integers representing the id of the node. The solution starts and ends with 0
            as the tour starts from the depot
    """
    # Variables
    # nb_of_iter = 100_000    # Stopping criteria 
    nb_of_iter = 100        # Stopping criteria 
    time_limit = 10*60      # Stopping criteria 
    nb_of_ants = 1          # n_of_ants: the number of ants
    l_rate = 0.1            # l_rate: the learning rate for pheromone values
    tau_min = 0.001         # lower limit for the pheromone values
    tau_max = 0.999         # upper limit for the pheromone values
    determinism_rate = 0.2  # rate of determinism in the solution construction
    nb_of_trials = 1        #  number of trials to be executed for the given problem instance
    beam_width = 1          # parameters for the beam procedure
    mu = 4.0                # stochastic sampling parameter
    max_children = 100      # stochastic sampling parameter #! NOT USED 
    n_samples = 10          # stochastic sampling parameter #! NOT USED 
    sample_percent = 100    # stochastic sampling parameter #! NOT USED 
    do_local_search = False # If the local search heuristic is executed

    tic = time.time()
    
    ant = Ant(tsptw, l_rate=l_rate, tau_max=tau_max, tau_min=tau_min)
    pbs = ProbabilisticBeamSearch(tsptw, ant, beam_width, determinism_rate, max_children, mu, n_samples, sample_percent)

    # To collec statistics
    best_solution = None
    results = list()
    violations = list()
    times_best_found = list()
    iter_best_found = list() 

    # Solution
    best_so_far_solution = None
    restart_best_solution = None
    iteration_best_solution = None

    ### For each trial for a number of trial
    with tqdm(total=nb_of_iter*nb_of_trials) as progress_bar:

        for trial_nb in range(nb_of_trials):
            #? Beam-ACO: algo #2 of the paper
            best_so_far_solution = None
            restart_best_solution = None
            ant.resetUniformPheromoneValues()
            bs_update = False
            restart = False
            time_local_search = 0.0
            solution_evaluation = 0

            ### algorithm: iterates main loop until a maximum CPU time limit is reached
            trial_tic = time.time()
            time_init = time.time()
            nb_iter_done = 0
            while nb_iter_done < nb_of_iter:

                if time.time() - time_init  > time_limit:
                    progress_bar.update(nb_of_iter - nb_iter_done)
                    break

                iteration_best_solution = None
                avg_cost = 0.0
                avg_violation = 0.0


                ### Probabilistic beam search algorithm is executed. This produces the iteration-best solution Pib
                for i in range(nb_of_ants):
                    #?  Probabilistic beam search: This part is the algo #1 of the paper
                    iteration_best_solution = pbs.beam_construct()
                    ### Then subject to the application of local search
                    while False and do_local_search:
                        new_solution = local_search(iteration_best_solution)
                        iteration_best_solution = get_best_soltion(new_solution, iteration_best_solution, tsptw)
                
                
                ### Updating the best-so-far solution
                trial_tac = time.time()
                if restart:
                    restart = False
                    restart_best_solution = None
                    best_so_far_solution = get_best_soltion(best_so_far_solution, iteration_best_solution, tsptw)    
                else:
                    restart_best_solution = get_best_soltion(iteration_best_solution, restart_best_solution, tsptw)
                    best_so_far_solution = get_best_soltion(best_so_far_solution, iteration_best_solution, tsptw)
                    
                best_soltion = get_best_soltion(best_solution, best_so_far_solution, tsptw)
                
                # Stats
                results.append(get_score(best_so_far_solution, tsptw))
                violations.append(get_number_of_violations(best_so_far_solution, tsptw))
                times_best_found.append(trial_tic-trial_tac)
                iter_best_found.append(trial_nb)
                
                
                ### A new value for the convergence factor cf is computed
                cf = ant.computeConvergenceFactor()
                
                
                ### Depending on cf and bs_update, a decision on whether to restart the algorithm or not is made
                if bs_update and cf > 0.99:
                    ant.resetUniformPheromoneValues()
                    bs_update = False
                    restart = True
                else:
                    if cf > 0.99:
                        bs_update = True
                    ant.updatePheromoneValues(bs_update, cf, iteration_best_solution, restart_best_solution, best_so_far_solution)
                
                trial_tic = time.time()
                nb_iter_done += 1
                progress_bar.update(1)
    
    print(f"results: {zip(results, violations)} \n")

    print(f"Number of violation: {get_number_of_violations(best_soltion, tsptw)}")
    print(f"Feasible solution: {tsptw.verify_solution(best_soltion)}")
    return best_soltion


def get_best_soltion(solution1, solution2, tsptw) -> List[int]:
    if solution1 == None and solution2 == None:
        return None
    if solution1 == None:
        return deepcopy(solution2)
    if solution2 == None:
        return deepcopy(solution1)
    return deepcopy(solution1) if get_score(solution1, tsptw) < get_score(solution2, tsptw) else deepcopy(solution2)


def get_score(solution: List[int], tsptw: TSPTW) -> int:   
    # ? Change for an estimation ? 
    return tsptw.get_solution_cost(solution)


def get_number_of_violations(solution: List[int], tsptw: TSPTW) -> int:
    nb_of_violation = 0
    time_step = 0
    last_stop = 0
    for next_stop in solution[1:]:
        edge = (last_stop, next_stop)
        time_step += tsptw.graph.edges[edge]["weight"]
        time_windows_begening, time_windows_end = tsptw.time_windows[next_stop]
        if  time_step < time_windows_begening:
            waiting_time = time_windows_begening - time_step
            time_step += waiting_time
        if time_step > time_windows_end:
            nb_of_violation += 1
    
    return nb_of_violation


def local_search(solution: List[int], tsptw: TSPTW) -> List[int]:
    #?: This part is the algo #3 of the paper
    # based on the 1-opt neighborhood in which a single customer is 
    # removed from the tour and reinserted in a different position
    p_best = deepcopy(solution)

    for k in range(tsptw.num_nodes - 1):
        p_test = deepcopy(solution)
        if not is_time_window_infeasible(p_test[k], p_test[k+1], p_test, tsptw):
            p_test = swap(p_test, k) # Algo #4
            p_best = get_best_soltion(p_Test, p_best)
            p_test2 = p_test
            for d in range(k+1, tsptw.num_nodes-1):
                if is_time_window_infeasible(p_test2[d], p_test2[d+1], p_test2, tsptw):
                    break
                p_test = swap(p_test, d)
                p_best = get_best_soltion(p_test, p_best)
            p_test = p_test2
            for d in range(k-1, 0):
                if is_time_window_infeasible(p_test2[d], p_test2[d+1], p_test2, tsptw):
                    break
                p_test = swap(p_test, d)
                p_best = get_best_soltion(p_test, p_best)
    
    return p_best

    raise Exception(f"{local_search.__name__} is not implemented")


def is_time_window_infeasible(last_stop: int, next_stop: int, solution: List[int], tsptw: TSPTW):
    raise Exception(f"{is_time_window_infeasible.__name__} is not implemented")


def swap(solution: List[int], k: int, tsptw: TSPTW) -> List[int]:
    solu_cost_old = tsptw.get_solution_cost(solution)
    violation_old = get_number_of_violations(solution, tsptw)
    cost = delta_c(solution, k, tsptw)
    # if tsptw.time_windows[]


    raise Exception(f"{swap.__name__} is not implemented")

def delta_c(solution: List[int], k: int, tsptw: TSPTW):
    cost = sum([tsptw.graph.edges[(solution[idx], solution[idx+1])]["weight"] for idx in range(k, tsptw.num_nodes-1)])
    cost -= sum([tsptw.graph.edges[(solution[idx], solution[idx+1])]["weight"] for idx in range(k, 0)])
    return cost
