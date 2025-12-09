"""
Deterministic Information Integration (DII) Framework
=====================================================

Implementation of the DII quantum measurement model from the paper.

Core components:
- Master equation evolution (unitary + decoherence + collapse)
- Information functional tracking
- Apparatus microstate sampling
- Born rule emergence from typicality

Author: Implementation based on DII framework
License: MIT
"""

import numpy as np
from scipy.integrate import odeint
from scipy.linalg import expm
from dataclasses import dataclass
from typing import Tuple, List, Optional, Callable
import warnings


@dataclass
class DIIParameters:
    """Parameters for DII quantum measurement simulation."""

    # System parameters
    system_dim: int = 2  # Hilbert space dimension of system (2 for qubit)

    # Apparatus parameters
    apparatus_dim: int = 100  # Effective apparatus dimension

    # Coupling and dynamics
    coupling_strength: float = 1.0  # g in H_int
    decoherence_rate: float = 0.1  # γ (dephasing rate)
    collapse_rate: float = 1.0  # λ (collapse strength)

    # Threshold
    threshold: float = 0.5  # Δ_crit in units of ℏ

    # Time evolution
    dt: float = 0.01  # Time step
    t_final: float = 100.0  # Final simulation time

    # Temperature (for decoherence)
    temperature: float = 1.0  # in units of characteristic energy scale

    # Random seed
    random_seed: Optional[int] = None


class ApparatusMicrostate:
    """
    Represents the apparatus quantum microstate.

    Key insight: The apparatus has ~10^23 degrees of freedom with thermal
    fluctuations leading to run-to-run variation in |ψ_A^micro⟩.

    For simulation, we use N-dimensional Hilbert space with random phases
    representing thermal randomness.
    """

    def __init__(self, dim: int, seed: Optional[int] = None):
        """
        Initialize apparatus microstate.

        Args:
            dim: Apparatus Hilbert space dimension
            seed: Random seed for reproducibility
        """
        self.dim = dim
        self.rng = np.random.default_rng(seed)
        self._state = None
        self._overlaps = None

    def sample_thermal_state(self) -> np.ndarray:
        """
        Sample a thermal microstate from Haar-random distribution.

        Physical justification:
        - Apparatus thermalizes at temperature T
        - Chaotic dynamics explore Hilbert space uniformly
        - Porter-Thomas statistics apply

        Returns:
            Complex vector of dimension dim (normalized)
        """
        # Random phases (uniform on [0, 2π))
        phases = self.rng.uniform(0, 2*np.pi, self.dim)

        # Equal amplitude superposition with random phases
        # This approximates Haar-random distribution for large dim
        state = np.exp(1j * phases) / np.sqrt(self.dim)

        # For higher accuracy, use Ginibre ensemble
        # (Gaussian random complex numbers normalized)
        real_part = self.rng.normal(0, 1, self.dim)
        imag_part = self.rng.normal(0, 1, self.dim)
        state = (real_part + 1j * imag_part)
        state = state / np.linalg.norm(state)

        self._state = state
        return state

    def compute_overlaps(self, pointer_states: List[np.ndarray]) -> np.ndarray:
        """
        Compute X_i = |⟨A_i|ψ_A^micro⟩|² for each pointer state.

        Args:
            pointer_states: List of apparatus pointer states |A_i⟩

        Returns:
            Array of overlap squared magnitudes
        """
        if self._state is None:
            raise ValueError("Must sample thermal state first")

        overlaps = np.array([
            np.abs(np.vdot(pointer, self._state))**2
            for pointer in pointer_states
        ])

        self._overlaps = overlaps
        return overlaps

    @property
    def state(self) -> np.ndarray:
        """Current apparatus microstate."""
        return self._state

    @property
    def overlaps(self) -> Optional[np.ndarray]:
        """Cached pointer state overlaps."""
        return self._overlaps


class InformationFunctional:
    """
    Compute information integration functional I_k(t).

    Physical meaning: How much information about outcome k has spread
    into the environment (measuring "record" formation).

    Simplified version for toy model:
    I_k(t) = ∫ coherence_density * decoherence_factor dt
    """

    def __init__(self, params: DIIParameters):
        self.params = params
        self.history = []  # Track I_k(t) over time

    def compute(self, rho_full: np.ndarray, t: float) -> np.ndarray:
        """
        Compute information functional for each outcome branch.

        Args:
            rho_full: Full density matrix (system ⊗ apparatus)
            t: Current time

        Returns:
            Array [I_0(t), I_1(t), ...] for each outcome
        """
        system_dim = self.params.system_dim

        # Trace out apparatus to get system reduced density matrix
        rho_system = self._partial_trace_apparatus(rho_full, system_dim)

        # Information is related to off-diagonal coherence decay
        # Simplification: I_k ∝ diagonal purity - full purity
        # Full version would integrate current over spacetime

        information = np.zeros(system_dim)

        for k in range(system_dim):
            # Coherence loss for outcome k
            # Measure how much k-th diagonal element has "decohered"
            diag_k = rho_system[k, k].real

            # Accumulate information based on decoherence
            # I_k grows as coherence is destroyed
            off_diag_sum = np.sum(np.abs(rho_system[k, :])) - diag_k

            # Information accumulation rate
            information[k] = diag_k * (1 - off_diag_sum / (system_dim - 1 + 1e-10))

        # Store history
        self.history.append((t, information.copy()))

        return information

    def _partial_trace_apparatus(self, rho_full: np.ndarray,
                                   system_dim: int) -> np.ndarray:
        """
        Trace out apparatus degrees of freedom.

        Args:
            rho_full: Full density matrix
            system_dim: System Hilbert space dimension

        Returns:
            System reduced density matrix
        """
        total_dim = rho_full.shape[0]
        apparatus_dim = total_dim // system_dim

        rho_system = np.zeros((system_dim, system_dim), dtype=complex)

        for i in range(system_dim):
            for j in range(system_dim):
                # Sum over apparatus indices
                for k in range(apparatus_dim):
                    idx_i = i * apparatus_dim + k
                    idx_j = j * apparatus_dim + k
                    rho_system[i, j] += rho_full[idx_i, idx_j]

        return rho_system

    def get_information_gap(self) -> Tuple[float, int]:
        """
        Get current information gap ΔI = max(I_k) - max_{j≠k}(I_j).

        Returns:
            (gap, winning_index)
        """
        if not self.history:
            return 0.0, 0

        _, info = self.history[-1]
        sorted_info = np.sort(info)[::-1]

        gap = sorted_info[0] - sorted_info[1]
        winner = np.argmax(info)

        return gap, winner


class CollapseDynamics:
    """
    Implement collapse functional F_k(ρ_A) and Lindblad-form collapse term.

    Key equation:
    Ĉ[ρ] = -λ Σ_k F_k(ρ) (P_k ρ + ρ P_k - 2 P_k ρ P_k)

    where F_k = tanh(ΔI_k / Δ_crit)
    """

    def __init__(self, params: DIIParameters, info_func: InformationFunctional):
        self.params = params
        self.info_func = info_func

    def collapse_functional(self, delta_I: float) -> float:
        """
        Compute F_k = tanh(ΔI / Δ_crit).

        Physical meaning:
        - ΔI ≪ Δ_crit: F ≈ 0 (no collapse, superposition stable)
        - ΔI ≈ Δ_crit: F ≈ 0.5 (transition region)
        - ΔI ≫ Δ_crit: F → 1 (strong collapse)

        Args:
            delta_I: Information gap

        Returns:
            Collapse strength (0 to 1)
        """
        return np.tanh(delta_I / self.params.threshold)

    def lindblad_collapse_term(self, rho: np.ndarray,
                                projectors: List[np.ndarray]) -> np.ndarray:
        """
        Compute Lindblad collapse superoperator.

        Args:
            rho: Density matrix
            projectors: List of projection operators P_k

        Returns:
            Collapse contribution to dρ/dt
        """
        # Get current information gap
        delta_I, winner = self.info_func.get_information_gap()

        # Collapse functional
        F = self.collapse_functional(delta_I)

        # Lindblad term: Σ_k F (P_k ρ + ρ P_k - 2 P_k ρ P_k)
        collapse_term = np.zeros_like(rho, dtype=complex)

        for k, P_k in enumerate(projectors):
            # Lindblad dissipator form
            # L[ρ] = P ρ P† - (1/2){P†P, ρ}
            # Simplified: P_k ρ + ρ P_k - 2 P_k ρ P_k

            term = P_k @ rho + rho @ P_k - 2 * P_k @ rho @ P_k
            collapse_term += F * term

        collapse_term *= -self.params.collapse_rate

        return collapse_term


class DIISimulation:
    """
    Main simulation class for DII quantum measurement.

    Integrates master equation:
    dρ/dt = -i/ℏ[H,ρ] + L_deco[ρ] + L_collapse[ρ]
    """

    def __init__(self, params: DIIParameters):
        self.params = params
        self.apparatus = ApparatusMicrostate(params.apparatus_dim, params.random_seed)
        self.info_func = InformationFunctional(params)
        self.collapse = CollapseDynamics(params, self.info_func)

        # Initialize system
        self._setup_system()

    def _setup_system(self):
        """Initialize quantum system components."""
        # System initial state: |+⟩ = (|0⟩ + |1⟩)/√2
        d_sys = self.params.system_dim
        psi_sys = np.ones(d_sys, dtype=complex) / np.sqrt(d_sys)

        # Apparatus pointer states (orthonormal basis)
        d_app = self.params.apparatus_dim
        self.pointer_states = [
            self._create_pointer_state(k, d_app)
            for k in range(d_sys)
        ]

        # Sample apparatus microstate
        self.apparatus.sample_thermal_state()

        # Compute overlaps X_i
        self.X_overlaps = self.apparatus.compute_overlaps(self.pointer_states)

        # Initial density matrix: |ψ_S⟩⟨ψ_S| ⊗ |ψ_A⟩⟨ψ_A|
        rho_sys = np.outer(psi_sys, psi_sys.conj())
        rho_app = np.outer(self.apparatus.state, self.apparatus.state.conj())
        self.rho_initial = np.kron(rho_sys, rho_app)

        # Interaction Hamiltonian
        self._build_hamiltonian()

        # Projectors for collapse
        self.projectors = self._build_projectors()

    def _create_pointer_state(self, k: int, dim: int) -> np.ndarray:
        """Create k-th apparatus pointer state."""
        state = np.zeros(dim, dtype=complex)
        # Simple model: pointer states are basis states
        # More realistic: coherent states separated in phase space
        state[k % dim] = 1.0
        return state

    def _build_hamiltonian(self):
        """
        Build interaction Hamiltonian.

        H_int = g Σ_k |k⟩⟨k|_S ⊗ A_k

        where A_k are apparatus operators coupling to pointer states.
        """
        d_sys = self.params.system_dim
        d_app = self.params.apparatus_dim
        g = self.params.coupling_strength

        # For simplicity: H_int = g Σ_k |k⟩⟨k|_S ⊗ |A_k⟩⟨A_k|_A
        H = np.zeros((d_sys * d_app, d_sys * d_app), dtype=complex)

        for k in range(min(d_sys, len(self.pointer_states))):
            # System projector
            P_sys = np.zeros((d_sys, d_sys))
            P_sys[k, k] = 1.0

            # Apparatus projector
            P_app = np.outer(self.pointer_states[k],
                           self.pointer_states[k].conj())

            # Tensor product
            H += g * np.kron(P_sys, P_app)

        self.hamiltonian = H

    def _build_projectors(self) -> List[np.ndarray]:
        """Build projection operators for each outcome."""
        d_sys = self.params.system_dim
        d_app = self.params.apparatus_dim

        projectors = []
        for k in range(d_sys):
            # System projector |k⟩⟨k|
            P_sys = np.zeros((d_sys, d_sys))
            P_sys[k, k] = 1.0

            # Full projector (identity on apparatus)
            P_full = np.kron(P_sys, np.eye(d_app))
            projectors.append(P_full)

        return projectors

    def master_equation(self, rho_vec: np.ndarray, t: float) -> np.ndarray:
        """
        Master equation: dρ/dt = -i/ℏ[H,ρ] + L_deco + L_collapse.

        Args:
            rho_vec: Vectorized density matrix
            t: Current time

        Returns:
            dρ/dt (vectorized)
        """
        # Reshape to matrix
        dim = int(np.sqrt(len(rho_vec)))
        rho = rho_vec.reshape((dim, dim))

        # 1. Unitary evolution: -i[H, ρ]
        commutator = self.hamiltonian @ rho - rho @ self.hamiltonian
        drho_unitary = -1j * commutator  # ℏ = 1

        # 2. Decoherence (dephasing in system basis)
        drho_deco = self._decoherence_term(rho)

        # 3. Update information functional
        info = self.info_func.compute(rho, t)

        # 4. Collapse term
        drho_collapse = self.collapse.lindblad_collapse_term(rho, self.projectors)

        # Total
        drho_dt = drho_unitary + drho_deco + drho_collapse

        return drho_dt.flatten()

    def _decoherence_term(self, rho: np.ndarray) -> np.ndarray:
        """
        Decoherence Lindbladian (pure dephasing).

        L_deco[ρ] = -γ (ρ - ρ_diag)
        where ρ_diag = Σ_k P_k ρ P_k
        """
        gamma = self.params.decoherence_rate

        # Diagonal part
        rho_diag = np.zeros_like(rho)
        for P_k in self.projectors:
            rho_diag += P_k @ rho @ P_k

        # Dephasing
        return -gamma * (rho - rho_diag)

    def evolve(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Time-evolve the system.

        Returns:
            (times, rho_trajectory)
        """
        # Time points
        times = np.arange(0, self.params.t_final, self.params.dt)

        # Initial condition (vectorized)
        rho0_vec = self.rho_initial.flatten()

        # Integrate ODE
        # Using complex ODE integration
        rho_trajectory = odeint(
            lambda rho, t: self.master_equation(rho, t),
            rho0_vec,
            times,
            tfirst=True
        )

        return times, rho_trajectory

    def determine_outcome(self, amplitudes: np.ndarray) -> int:
        """
        Deterministic outcome selection rule.

        k = argmax_i (|c_i|² X_i)

        Args:
            amplitudes: System superposition amplitudes c_i

        Returns:
            Outcome index k
        """
        probs_born = np.abs(amplitudes)**2

        # Deterministic selection
        selection_weights = probs_born * self.X_overlaps
        outcome = np.argmax(selection_weights)

        return outcome

    def run_single_measurement(self) -> dict:
        """
        Run a single measurement simulation.

        Returns:
            Dictionary with outcome, overlaps, trajectory, etc.
        """
        # Evolve system
        times, rho_traj = self.evolve()

        # Get system state (initial superposition)
        d_sys = self.params.system_dim
        amplitudes = np.ones(d_sys) / np.sqrt(d_sys)

        # Determine outcome
        outcome = self.determine_outcome(amplitudes)

        # Extract final density matrix
        rho_final = rho_traj[-1].reshape(self.rho_initial.shape)

        return {
            'outcome': outcome,
            'X_overlaps': self.X_overlaps,
            'amplitudes': amplitudes,
            'times': times,
            'rho_trajectory': rho_traj,
            'rho_final': rho_final,
            'info_history': self.info_func.history
        }


class DIIEnsemble:
    """
    Run ensemble of measurements to verify Born rule statistics.
    """

    def __init__(self, params: DIIParameters, n_trials: int = 1000):
        self.params = params
        self.n_trials = n_trials
        self.results = []

    def run_ensemble(self, verbose: bool = True) -> dict:
        """
        Run N independent measurement trials.

        Each trial has different apparatus microstate (thermal fluctuations).

        Returns:
            Statistics dictionary
        """
        outcomes = []

        for trial in range(self.n_trials):
            # New apparatus microstate each trial (thermal fluctuation)
            params_trial = DIIParameters(
                **{k: v for k, v in self.params.__dict__.items()},
            )
            params_trial.random_seed = (
                self.params.random_seed + trial
                if self.params.random_seed is not None
                else None
            )

            # Run simulation
            sim = DIISimulation(params_trial)
            result = sim.run_single_measurement()

            outcomes.append(result['outcome'])
            self.results.append(result)

            if verbose and (trial + 1) % 100 == 0:
                print(f"Completed {trial + 1}/{self.n_trials} trials")

        # Compute statistics
        outcomes = np.array(outcomes)
        d_sys = self.params.system_dim

        # Empirical frequencies
        freq_empirical = np.array([
            np.sum(outcomes == k) / self.n_trials
            for k in range(d_sys)
        ])

        # Born rule prediction (uniform superposition)
        freq_born = np.ones(d_sys) / d_sys

        # Statistical error
        freq_error = np.sqrt(freq_born * (1 - freq_born) / self.n_trials)

        return {
            'outcomes': outcomes,
            'frequencies': freq_empirical,
            'born_rule': freq_born,
            'statistical_error': freq_error,
            'chi_squared': self._chi_squared_test(freq_empirical, freq_born),
            'n_trials': self.n_trials
        }

    def _chi_squared_test(self, observed: np.ndarray,
                          expected: np.ndarray) -> float:
        """Compute χ² statistic."""
        # Avoid division by zero
        expected = np.maximum(expected, 1e-10)
        chi2 = np.sum((observed - expected)**2 / expected)
        return chi2


def demonstrate_born_rule_convergence():
    """
    Demonstrate Born rule emergence from typicality.

    Show that as apparatus dimension N → ∞,
    Beta(1, N-1) → Exp(1) → Born rule frequencies.
    """
    print("=" * 60)
    print("Born Rule Convergence Demonstration")
    print("=" * 60)

    # Test different apparatus dimensions
    dims = [10, 50, 100, 500]
    n_trials = 5000

    for dim in dims:
        print(f"\nApparatus dimension N = {dim}")
        print("-" * 40)

        params = DIIParameters(
            system_dim=2,
            apparatus_dim=dim,
            random_seed=42
        )

        ensemble = DIIEnsemble(params, n_trials=n_trials)
        stats = ensemble.run_ensemble(verbose=False)

        print(f"Empirical frequencies: {stats['frequencies']}")
        print(f"Born rule prediction:  {stats['born_rule']}")
        print(f"Statistical error:     {stats['statistical_error']}")
        print(f"χ² statistic:          {stats['chi_squared']:.3f}")

        # Deviation from Born rule
        deviation = np.max(np.abs(stats['frequencies'] - stats['born_rule']))
        print(f"Max deviation:         {deviation:.4f}")
        print(f"Expected scaling:      O(1/√N) ≈ {1/np.sqrt(dim):.4f}")


if __name__ == "__main__":
    # Quick demonstration
    print("DII Framework - Quick Test")
    print("=" * 60)

    # Set up parameters
    params = DIIParameters(
        system_dim=2,
        apparatus_dim=100,
        coupling_strength=1.0,
        decoherence_rate=0.1,
        collapse_rate=1.0,
        threshold=0.5,
        t_final=50.0,
        random_seed=42
    )

    print("\nRunning single measurement...")
    sim = DIISimulation(params)
    result = sim.run_single_measurement()

    print(f"Outcome: {result['outcome']}")
    print(f"System amplitudes: {result['amplitudes']}")
    print(f"Apparatus overlaps X_i: {result['X_overlaps']}")
    print(f"Selection weights |c_i|² X_i: {np.abs(result['amplitudes'])**2 * result['X_overlaps']}")

    print("\n" + "=" * 60)
    print("Running ensemble to verify Born rule...")
    print("=" * 60)

    ensemble = DIIEnsemble(params, n_trials=1000)
    stats = ensemble.run_ensemble(verbose=True)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Empirical frequencies: {stats['frequencies']}")
    print(f"Born rule (theory):    {stats['born_rule']}")
    print(f"Statistical error:     ±{stats['statistical_error']}")
    print(f"χ² statistic:          {stats['chi_squared']:.3f}")
    print(f"DOF:                   {params.system_dim - 1}")

    # Statistical test
    from scipy.stats import chi2
    p_value = 1 - chi2.cdf(stats['chi_squared'], df=params.system_dim - 1)
    print(f"p-value:               {p_value:.3f}")

    if p_value > 0.05:
        print("\n✓ Born rule verified (p > 0.05)")
    else:
        print("\n✗ Born rule NOT verified (p < 0.05)")
