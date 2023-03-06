from typing import List, Tuple
from tsptw import TSPTW
from utils.ant import Ant
import numpy as np
from math import inf

from utils.beam_node import BeamNode

class ProbabilisticBeamSearch():

    def __init__(self, 
                 tsptw: TSPTW, 
                 ant: Ant, 
                 beam_width: int = 1, 
                 determinism_rate: float = 0.9, 
                 max_children: int = 100, 
                 mu: float = 0.2, 
                 n_samples: int = 10, 
                 sample_percent: int = 100):
        assert int(beam_width) > 0, "beam_width must be greater than 1"
        assert mu >= 1, "mu must be >= 1"
        self.tsptw: TSPTW = tsptw
        self.ant: Ant = ant
        self.beam_width = beam_width  # k_bw
        self.determinism_rate = determinism_rate
        self.max_children = max_children #! NOT USED 
        self.mu_k_bw = int(beam_width * mu)
        self.n_samples  = n_samples #! NOT USED 
        self.sample_rate = int((sample_percent * (tsptw.num_nodes - 1) / 100.0) + 0.5) + 1 #! NOT USED  


    def beam_construct(self) -> List[int]:
        depot_id = 0
        pheromone = self.ant.pheromone
        beam_root = BeamNode(depot_id, pheromone)
        self.__random_define_lambda()
        number_of_children_not_in_solution = self.tsptw.num_nodes - 1  # C := C(B_t) 
        # switch when Reduce is implemented self.__beam__construction_step(beam_root, number_of_children_not_in_solution) # for t := 0 to n (recursive)
        self.__beam__construction_step(beam_root, self.mu_k_bw, number_of_children_not_in_solution) # for t := 0 to n (recursive)

        potential_solutions = beam_root.extract_solution() 
        potential_solutions_cost = [self.tsptw.get_solution_cost(solution) for solution in potential_solutions]
        return potential_solutions[np.argmin(potential_solutions_cost)] + [0] # return argmin_lex{T | T in B_n}
        

    # switch when Reduce is implemented def __beam__construction_step(self, beam: BeamNode, number_of_children_not_in_solution: int) -> None:
    def __beam__construction_step(self, beam: BeamNode, mu_k_bw: int, number_of_children_not_in_solution: int) -> None:
        
        for _ in range(min(mu_k_bw, number_of_children_not_in_solution)):
            id_of_next_customer = self.__stochastic_sampling(beam.pheromone, beam.id)   # <P,j> := ChooseFrom(C
            child_node = BeamNode(id_of_next_customer, beam.pheromone)                  # B_{t+1} := B_t union <P,j> and C := C\<P,j>
            beam.children.add(child_node)
        # Todo: B_{t+1} := Reduce(B_{t+1}, k_bw)

        for beam_child in beam.children:
            # switch when Reduce is implemented self.__beam__construction_step(beam_child, number_of_children_not_in_solution-1) # for t := 0 to n (recursive)
            self.__beam__construction_step(beam_child, max(1, mu_k_bw-1), number_of_children_not_in_solution-1) # for t := 0 to n (recursive)

    
    def __stochastic_sampling(self, pheromone: List[List[float]], last_customer_added: int) -> int:
        """
        -> ChooseFrom(C) from the paper
        """
        # first generate a random number q uniformly distributed [0; 1] 
        q = np.random.uniform(0.0, 1.0)
        # Compare this value with the determinism rate
        tau_eta = (np.array(pheromone) *  np.array(self.__sample_heuristic_benefit_of_visiting_customer()))[last_customer_added]
        if q <= self.determinism_rate:
            # j in N(P) is choosen deterministically as costumer with highest product of pheromone and heuristic
            return np.argmax(tau_eta)
        else:
            # j stochastically chosen from the following distribtion
            p = (tau_eta / sum(tau_eta))
            return np.random.choice([i for i in range(len(tau_eta))], p=p)
    

    def __sample_heuristic_benefit_of_visiting_customer(self) -> np.ndarray[np.floating]:
        """
        Regarding the definition of n_ij, several existing greedy functions for the TSPTW may be used for that purpose
        To decide which customer should be visited next: small travel cost between customers is desirable
        but also those customers whose time window finishes sooner should be given priority to avoid constraint violations
            * combines travel cost: c_ij
            * lastest service time: l_j
            * earliest service time: e_k
        """                 
        c, l, e = self.__heuristic_benefit_of_visiting_customer_attributes
        eta = self.lambda_c * c + self.lambda_l * l + self.lambda_e * e

        return eta
    
    def __random_define_lambda(self):
        self.lambda_c = np.random.uniform(0, 1.0)
        self.lambda_l = np.random.uniform(0, 1.0-self.lambda_c)
        self.lambda_e = 1.0 - self.lambda_c - self.lambda_l

    @property
    def __heuristic_benefit_of_visiting_customer_attributes(self) -> Tuple[np.ndarray[np.floating], np.ndarray[np.floating], np.ndarray[np.floating]]:
        """ Return standardize c, l, and e from equation 4 """
        if not hasattr(self, "travel_cost") or not hasattr(self, "lastest_service_time") or not hasattr(self, "earliest_service_time"):
            self.travel_cost = np.zeros(self.ant.pheromone.shape, float)
            standardizer = s if (s:=self.tsptw.distance_max - self.tsptw.distance_min) > 0 else 1
            for i in range(self.ant.n):
                for j in range(self.ant.n):
                    self.travel_cost[i][j] = (self.tsptw.distance_max - self.tsptw.graph.edges[(i,j)]['weight']) / standardizer
                self.travel_cost[i][i] = 0

            self.earliest_service_time = np.zeros(self.ant.pheromone.shape, float)
            self.lastest_service_time = np.zeros(self.ant.pheromone.shape, float)
            e_max, l_max, e_min, l_min = -1.0, -1.0, inf, inf
            for i in range(self.ant.n):
                i_earliest_windows = float(self.tsptw.time_windows[i][0])
                i_lastest_windows  = float(self.tsptw.time_windows[i][1])
                e_j, l_j = inf, inf

                for j in range(self.ant.n):
                    if j != i:
                        earliest_time_windows = float(self.tsptw.time_windows[j][0]) - i_earliest_windows
                        lastest_time_windows  = float(self.tsptw.time_windows[j][1]) - i_lastest_windows
                        if earliest_time_windows > 0:
                            e_j = min(e_j, earliest_time_windows)
                        if lastest_time_windows > 0:
                            l_j = min(l_j, lastest_time_windows)

                self.earliest_service_time[:, i] = e_j if e_j != inf else 0.
                self.lastest_service_time[:, i]  = l_j if l_j != inf else 0.
            
                e_max = max(e_max, e_j) if e_j != inf else e_max
                e_min = min(e_min, e_j) if e_j != inf else e_min
                l_max = max(l_max, l_j) if l_j != inf else l_max
                l_min = min(l_min, l_j) if l_j != inf else l_min

            # Standardize
            self.earliest_service_time = (e_max - self.earliest_service_time) / (e_max - e_min)
            self.lastest_service_time  = (l_max - self.lastest_service_time ) / (l_max - l_min) 
            for i in range(self.ant.n):
                if self.earliest_service_time[0, i] > 1.0:
                    self.earliest_service_time[:, i] = 1.0
                if self.earliest_service_time[0, i] == 0.:
                    self.earliest_service_time[:, i] = 0.001
                if self.lastest_service_time[0, i] > 1.0:
                    self.lastest_service_time[:, i] = 1.0
                if self.lastest_service_time[0, i] == 0.:
                    self.lastest_service_time[:, i] = 0.001
        
        return self.travel_cost, self.lastest_service_time, self.earliest_service_time
