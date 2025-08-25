"""
Monte Carlo simulation and risk analysis interfaces.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple
import pandas as pd

from ..models.trading import ProcessedTrade


class IMonteCarloSimulator(ABC):
    """Interface for Monte Carlo simulation."""
    
    @abstractmethod
    def run_simulation(self, trades: List[ProcessedTrade], num_simulations: int = 10000, 
                      time_horizon: int = 252) -> Dict[str, Any]:
        """Run Monte Carlo simulation on trading data."""
        pass
    
    @abstractmethod
    def generate_scenarios(self, historical_returns: List[float], 
                         num_scenarios: int) -> List[List[float]]:
        """Generate scenario paths for simulation."""
        pass
    
    @abstractmethod
    def simulate_portfolio_performance(self, scenarios: List[List[float]], 
                                     initial_capital: float) -> List[float]:
        """Simulate portfolio performance across scenarios."""
        pass


class IRiskCalculator(ABC):
    """Interface for risk metrics calculation."""
    
    @abstractmethod
    def calculate_var(self, returns: List[float], confidence_level: float = 0.05) -> float:
        """Calculate Value at Risk (VaR)."""
        pass
    
    @abstractmethod
    def calculate_expected_shortfall(self, returns: List[float], 
                                   confidence_level: float = 0.05) -> float:
        """Calculate Expected Shortfall (Conditional VaR)."""
        pass
    
    @abstractmethod
    def calculate_risk_metrics(self, simulation_results: List[float]) -> Dict[str, float]:
        """Calculate comprehensive risk metrics from simulation results."""
        pass


class IScenarioGenerator(ABC):
    """Interface for scenario generation."""
    
    @abstractmethod
    def estimate_parameters(self, historical_data: List[float]) -> Dict[str, float]:
        """Estimate distribution parameters from historical data."""
        pass
    
    @abstractmethod
    def generate_correlated_scenarios(self, assets_data: Dict[str, List[float]], 
                                    num_scenarios: int) -> Dict[str, List[List[float]]]:
        """Generate correlated scenarios for multiple assets."""
        pass
    
    @abstractmethod
    def validate_scenarios(self, scenarios: List[List[float]], 
                         historical_data: List[float]) -> Dict[str, float]:
        """Validate generated scenarios against historical data."""
        pass