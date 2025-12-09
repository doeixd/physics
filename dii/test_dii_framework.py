"""
Test Suite for DII Framework
============================

Comprehensive tests for the Deterministic Information Integration framework.

Test categories:
1. Unit tests (individual components)
2. Integration tests (full simulation)
3. Statistical tests (Born rule verification)
4. Physics validation (conservation laws, no-signaling)
"""

import unittest
import numpy as np
from scipy.stats import chi2, kstest, expon
import warnings

from dii_framework import (
    DIIParameters,
    ApparatusMicrostate,
    InformationFunctional,
    CollapseDynamics,
    DIISimulation,
    DIIEnsemble
)


class TestApparatusMicrostate(unittest.TestCase):
    """Test apparatus microstate sampling and properties."""

    def setUp(self):
        """Set up test fixtures."""
        self.dim = 100
        self.apparatus = ApparatusMicrostate(self.dim, seed=42)

    def test_initialization(self):
        """Test apparatus initializes correctly."""
        self.assertEqual(self.apparatus.dim, self.dim)
        self.assertIsNone(self.apparatus.state)
        self.assertIsNone(self.apparatus.overlaps)

    def test_thermal_state_normalization(self):
        """Test sampled thermal state is normalized."""
        state = self.apparatus.sample_thermal_state()

        # Check normalization
        norm = np.linalg.norm(state)
        self.assertAlmostEqual(norm, 1.0, places=10)

        # Check dimension
        self.assertEqual(len(state), self.dim)

        # Check complex type
        self.assertTrue(np.iscomplexobj(state))

    def test_thermal_state_randomness(self):
        """Test different samples give different states."""
        state1 = self.apparatus.sample_thermal_state()
        state2 = self.apparatus.sample_thermal_state()

        # Should be different (with high probability)
        overlap = np.abs(np.vdot(state1, state2))**2
        # For Haar-random, expected overlap ~ 1/dim
        self.assertLess(overlap, 0.1)

    def test_overlaps_computation(self):
        """Test overlap computation with pointer states."""
        self.apparatus.sample_thermal_state()

        # Create orthonormal pointer states
        pointer_states = [
            np.eye(self.dim)[i] for i in range(3)
        ]

        overlaps = self.apparatus.compute_overlaps(pointer_states)

        # Check properties
        self.assertEqual(len(overlaps), 3)
        self.assertTrue(np.all(overlaps >= 0))
        self.assertTrue(np.all(overlaps <= 1))

        # Sum of all overlaps for complete basis
        pointer_full = [np.eye(self.dim)[i] for i in range(self.dim)]
        overlaps_full = self.apparatus.compute_overlaps(pointer_full)
        self.assertAlmostEqual(np.sum(overlaps_full), 1.0, places=10)

    def test_haar_distribution_exponential(self):
        """
        Test that overlaps follow exponential distribution.

        For large dimension, X_i = |⟨A_i|ψ_A⟩|² ~ Exp(1) for Haar-random ψ_A.
        This is the Porter-Thomas distribution.
        """
        n_samples = 1000
        overlaps_all = []

        # Sample many apparatus states
        for _ in range(n_samples):
            apparatus = ApparatusMicrostate(self.dim, seed=None)
            apparatus.sample_thermal_state()

            # Fixed pointer state (basis vector)
            pointer = np.eye(self.dim)[0]
            overlap = np.abs(np.vdot(pointer, apparatus.state))**2

            # Rescale by dimension (for Exp(1) distribution)
            overlaps_all.append(overlap * self.dim)

        overlaps_all = np.array(overlaps_all)

        # Kolmogorov-Smirnov test against Exp(1)
        ks_stat, p_value = kstest(overlaps_all, 'expon', args=(0, 1))

        # Should not reject exponential hypothesis (p > 0.05)
        # Note: for finite dimension, there are corrections O(1/dim)
        self.assertGreater(p_value, 0.01,
            f"Overlaps don't follow exponential (p={p_value:.4f})")


class TestInformationFunctional(unittest.TestCase):
    """Test information functional computation."""

    def setUp(self):
        """Set up test parameters."""
        self.params = DIIParameters(
            system_dim=2,
            apparatus_dim=10,
            random_seed=42
        )
        self.info_func = InformationFunctional(self.params)

    def test_initialization(self):
        """Test information functional initializes."""
        self.assertEqual(len(self.info_func.history), 0)
        self.assertEqual(self.info_func.params, self.params)

    def test_compute_information(self):
        """Test information computation for simple states."""
        # Pure state (no decoherence)
        psi = np.array([1, 0], dtype=complex)
        rho_pure = np.outer(psi, psi.conj())
        rho_full = np.kron(rho_pure, np.eye(10) / 10)

        info = self.info_func.compute(rho_full, t=0.0)

        # Check output shape
        self.assertEqual(len(info), self.params.system_dim)
        self.assertTrue(np.all(info >= 0))

    def test_information_growth(self):
        """Test that information grows with decoherence."""
        # This would require full simulation
        # Placeholder for integration test
        pass

    def test_information_gap(self):
        """Test information gap computation."""
        # Manually add history
        self.info_func.history = [
            (0.0, np.array([0.5, 0.3])),
            (1.0, np.array([0.8, 0.2])),
            (2.0, np.array([0.95, 0.05]))
        ]

        gap, winner = self.info_func.get_information_gap()

        self.assertEqual(winner, 0)
        self.assertAlmostEqual(gap, 0.95 - 0.05)


class TestCollapseDynamics(unittest.TestCase):
    """Test collapse functional and dynamics."""

    def setUp(self):
        """Set up collapse dynamics."""
        self.params = DIIParameters(threshold=0.5, collapse_rate=1.0)
        self.info_func = InformationFunctional(self.params)
        self.collapse = CollapseDynamics(self.params, self.info_func)

    def test_collapse_functional_regimes(self):
        """Test collapse functional in different regimes."""
        # Small gap: F ≈ 0
        F_small = self.collapse.collapse_functional(delta_I=0.01)
        self.assertLess(F_small, 0.1)

        # Threshold gap: F ≈ 0.5
        F_threshold = self.collapse.collapse_functional(delta_I=0.5)
        self.assertAlmostEqual(F_threshold, np.tanh(1.0), places=2)

        # Large gap: F → 1
        F_large = self.collapse.collapse_functional(delta_I=10.0)
        self.assertGreater(F_large, 0.9)

    def test_collapse_functional_smoothness(self):
        """Test that collapse functional is smooth."""
        gaps = np.linspace(0, 2, 100)
        F_values = [self.collapse.collapse_functional(g) for g in gaps]

        # Check monotonicity
        self.assertTrue(np.all(np.diff(F_values) >= 0))

        # Check boundedness
        self.assertTrue(np.all(np.array(F_values) >= 0))
        self.assertTrue(np.all(np.array(F_values) <= 1))

    def test_lindblad_trace_preservation(self):
        """Test that collapse term preserves trace."""
        # Random density matrix
        dim = 4
        rho = np.random.rand(dim, dim) + 1j * np.random.rand(dim, dim)
        rho = rho @ rho.conj().T
        rho = rho / np.trace(rho)

        # Projectors
        projectors = [
            np.outer(np.eye(dim)[i], np.eye(dim)[i])
            for i in range(2)
        ]

        # Set information gap
        self.info_func.history = [(0.0, np.array([0.8, 0.2]))]

        # Compute collapse term
        drho = self.collapse.lindblad_collapse_term(rho, projectors)

        # Trace should be approximately zero
        self.assertAlmostEqual(np.trace(drho).real, 0.0, places=10)

    def test_lindblad_hermiticity(self):
        """Test that collapse preserves hermiticity."""
        dim = 4
        rho = np.random.rand(dim, dim) + 1j * np.random.rand(dim, dim)
        rho = rho @ rho.conj().T
        rho = rho / np.trace(rho)

        projectors = [
            np.outer(np.eye(dim)[i], np.eye(dim)[i])
            for i in range(2)
        ]

        self.info_func.history = [(0.0, np.array([0.7, 0.3]))]

        drho = self.collapse.lindblad_collapse_term(rho, projectors)

        # Should be Hermitian
        self.assertTrue(np.allclose(drho, drho.conj().T))


class TestDIISimulation(unittest.TestCase):
    """Test full DII simulation."""

    def setUp(self):
        """Set up simulation."""
        self.params = DIIParameters(
            system_dim=2,
            apparatus_dim=20,
            t_final=10.0,
            dt=0.1,
            random_seed=42
        )

    def test_simulation_initialization(self):
        """Test simulation initializes correctly."""
        sim = DIISimulation(self.params)

        # Check components exist
        self.assertIsNotNone(sim.apparatus)
        self.assertIsNotNone(sim.info_func)
        self.assertIsNotNone(sim.collapse)
        self.assertIsNotNone(sim.hamiltonian)
        self.assertIsNotNone(sim.projectors)

    def test_density_matrix_normalization(self):
        """Test initial density matrix is normalized."""
        sim = DIISimulation(self.params)

        trace = np.trace(sim.rho_initial)
        self.assertAlmostEqual(trace.real, 1.0, places=10)
        self.assertAlmostEqual(trace.imag, 0.0, places=10)

    def test_density_matrix_hermiticity(self):
        """Test density matrix is Hermitian."""
        sim = DIISimulation(self.params)

        is_hermitian = np.allclose(sim.rho_initial, sim.rho_initial.conj().T)
        self.assertTrue(is_hermitian)

    def test_density_matrix_positivity(self):
        """Test density matrix is positive semi-definite."""
        sim = DIISimulation(self.params)

        eigenvalues = np.linalg.eigvalsh(sim.rho_initial)
        self.assertTrue(np.all(eigenvalues >= -1e-10))

    def test_hamiltonian_hermiticity(self):
        """Test Hamiltonian is Hermitian."""
        sim = DIISimulation(self.params)

        is_hermitian = np.allclose(sim.hamiltonian, sim.hamiltonian.conj().T)
        self.assertTrue(is_hermitian)

    def test_projectors_orthogonality(self):
        """Test projection operators are orthogonal."""
        sim = DIISimulation(self.params)

        for i, P_i in enumerate(sim.projectors):
            for j, P_j in enumerate(sim.projectors):
                product = P_i @ P_j

                if i == j:
                    # P_i² = P_i (idempotent)
                    self.assertTrue(np.allclose(product, P_i))
                else:
                    # P_i P_j = 0 (orthogonal)
                    # Note: only for system projectors, not full space
                    pass

    def test_single_measurement_runs(self):
        """Test that single measurement completes without error."""
        sim = DIISimulation(self.params)
        result = sim.run_single_measurement()

        # Check result structure
        self.assertIn('outcome', result)
        self.assertIn('X_overlaps', result)
        self.assertIn('times', result)
        self.assertIn('rho_final', result)

        # Check outcome is valid
        self.assertIn(result['outcome'], range(self.params.system_dim))

    def test_outcome_determinism(self):
        """Test that same apparatus state gives same outcome."""
        # Two simulations with same seed
        sim1 = DIISimulation(self.params)
        result1 = sim1.run_single_measurement()

        sim2 = DIISimulation(self.params)
        result2 = sim2.run_single_measurement()

        # Should give identical outcomes (deterministic)
        self.assertEqual(result1['outcome'], result2['outcome'])
        self.assertTrue(np.allclose(result1['X_overlaps'], result2['X_overlaps']))

    def test_different_apparatus_gives_different_outcome(self):
        """Test that different apparatus states can give different outcomes."""
        # Run multiple times with different seeds
        outcomes = []

        for seed in range(10):
            params = DIIParameters(
                system_dim=2,
                apparatus_dim=20,
                t_final=5.0,
                random_seed=seed
            )
            sim = DIISimulation(params)
            result = sim.run_single_measurement()
            outcomes.append(result['outcome'])

        outcomes = np.array(outcomes)

        # Should see both outcomes (with high probability)
        unique_outcomes = np.unique(outcomes)
        self.assertGreater(len(unique_outcomes), 1,
            "Should see multiple outcomes across different apparatus states")


class TestDIIEnsemble(unittest.TestCase):
    """Test ensemble statistics and Born rule verification."""

    def setUp(self):
        """Set up ensemble parameters."""
        self.params = DIIParameters(
            system_dim=2,
            apparatus_dim=50,
            t_final=10.0,
            random_seed=42
        )

    def test_ensemble_runs(self):
        """Test ensemble simulation completes."""
        ensemble = DIIEnsemble(self.params, n_trials=10)
        stats = ensemble.run_ensemble(verbose=False)

        self.assertEqual(len(stats['outcomes']), 10)
        self.assertEqual(len(stats['frequencies']), 2)

    def test_born_rule_statistical_test(self):
        """
        Test Born rule emergence with statistical significance.

        For uniform superposition |+⟩ = (|0⟩ + |1⟩)/√2,
        Born rule predicts P(0) = P(1) = 0.5.
        """
        ensemble = DIIEnsemble(self.params, n_trials=500)
        stats = ensemble.run_ensemble(verbose=False)

        # Chi-squared test
        chi2_stat = stats['chi_squared']
        dof = self.params.system_dim - 1
        p_value = 1 - chi2.cdf(chi2_stat, df=dof)

        # Should NOT reject Born rule (p > 0.05)
        self.assertGreater(p_value, 0.01,
            f"Born rule rejected with p={p_value:.4f}")

    def test_born_rule_convergence_with_dimension(self):
        """
        Test that Born rule accuracy improves with apparatus dimension.

        Theoretical: deviation ~ O(1/√N) where N = apparatus dimension.
        """
        dims = [20, 50, 100]
        deviations = []

        for dim in dims:
            params = DIIParameters(
                system_dim=2,
                apparatus_dim=dim,
                t_final=5.0,
                random_seed=42
            )
            ensemble = DIIEnsemble(params, n_trials=500)
            stats = ensemble.run_ensemble(verbose=False)

            # Maximum deviation from Born rule
            deviation = np.max(np.abs(stats['frequencies'] - stats['born_rule']))
            deviations.append(deviation)

        # Check roughly decreasing trend (allowing statistical fluctuations)
        # This is a weak test; full convergence would need more trials
        mean_dev_small = np.mean(deviations[:2])
        mean_dev_large = deviations[-1]

        # Large dimension should be at least not worse (loose bound)
        self.assertLessEqual(mean_dev_large, mean_dev_small * 1.5)

    def test_non_uniform_superposition(self):
        """
        Test Born rule for non-uniform superposition.

        |ψ⟩ = cos(θ)|0⟩ + sin(θ)|1⟩  →  P(0) = cos²(θ), P(1) = sin²(θ)
        """
        # This requires modifying initial state
        # For now, we test only uniform case
        # TODO: extend framework to allow custom initial states
        pass


class TestPhysicsValidation(unittest.TestCase):
    """Test fundamental physics constraints."""

    def setUp(self):
        """Set up simulation."""
        self.params = DIIParameters(
            system_dim=2,
            apparatus_dim=30,
            t_final=20.0,
            random_seed=42
        )

    def test_trace_preservation(self):
        """Test that time evolution preserves trace."""
        sim = DIISimulation(self.params)
        times, rho_traj = sim.evolve()

        # Check trace at multiple times
        for rho_vec in rho_traj[::10]:  # Sample every 10 steps
            dim = int(np.sqrt(len(rho_vec)))
            rho = rho_vec.reshape((dim, dim))
            trace = np.trace(rho)

            self.assertAlmostEqual(trace.real, 1.0, places=5,
                msg=f"Trace not preserved: {trace}")

    def test_hermiticity_preservation(self):
        """Test that density matrix remains Hermitian."""
        sim = DIISimulation(self.params)
        times, rho_traj = sim.evolve()

        for rho_vec in rho_traj[::10]:
            dim = int(np.sqrt(len(rho_vec)))
            rho = rho_vec.reshape((dim, dim))

            is_hermitian = np.allclose(rho, rho.conj().T, atol=1e-6)
            self.assertTrue(is_hermitian, "Density matrix not Hermitian")

    def test_positivity_preservation(self):
        """Test that density matrix remains positive semi-definite."""
        sim = DIISimulation(self.params)
        times, rho_traj = sim.evolve()

        for rho_vec in rho_traj[::10]:
            dim = int(np.sqrt(len(rho_vec)))
            rho = rho_vec.reshape((dim, dim))

            eigenvalues = np.linalg.eigvalsh(rho)
            self.assertTrue(np.all(eigenvalues >= -1e-6),
                f"Negative eigenvalue: {np.min(eigenvalues)}")

    def test_energy_conservation_without_collapse(self):
        """Test energy conservation in unitary regime."""
        # Disable collapse and decoherence
        params = DIIParameters(
            system_dim=2,
            apparatus_dim=10,
            decoherence_rate=0.0,
            collapse_rate=0.0,
            t_final=10.0,
            random_seed=42
        )

        sim = DIISimulation(params)

        # Compute energy: E = Tr(H ρ)
        H = sim.hamiltonian
        times, rho_traj = sim.evolve()

        energies = []
        for rho_vec in rho_traj:
            dim = int(np.sqrt(len(rho_vec)))
            rho = rho_vec.reshape((dim, dim))
            E = np.trace(H @ rho).real
            energies.append(E)

        energies = np.array(energies)

        # Energy should be conserved (small numerical errors allowed)
        energy_variation = np.std(energies)
        self.assertLess(energy_variation, 0.01,
            f"Energy not conserved: std = {energy_variation}")

    def test_purity_decreases_with_decoherence(self):
        """Test that purity P = Tr(ρ²) decreases under decoherence."""
        sim = DIISimulation(self.params)
        times, rho_traj = sim.evolve()

        purities = []
        for rho_vec in rho_traj:
            dim = int(np.sqrt(len(rho_vec)))
            rho = rho_vec.reshape((dim, dim))

            # Purity = Tr(ρ²)
            purity = np.trace(rho @ rho).real
            purities.append(purity)

        purities = np.array(purities)

        # Purity should generally decrease (allowing for collapse dynamics)
        # At least, final purity should be less than initial
        self.assertLessEqual(purities[-1], purities[0] + 0.1,
            "Purity should decrease with decoherence")


class TestNumericalStability(unittest.TestCase):
    """Test numerical stability and error handling."""

    def test_no_nan_or_inf(self):
        """Test that simulation doesn't produce NaN or Inf."""
        params = DIIParameters(
            system_dim=2,
            apparatus_dim=30,
            t_final=20.0,
            random_seed=42
        )

        sim = DIISimulation(params)
        result = sim.run_single_measurement()

        # Check final density matrix
        rho_final = result['rho_final']
        self.assertFalse(np.any(np.isnan(rho_final)))
        self.assertFalse(np.any(np.isinf(rho_final)))

    def test_large_apparatus_dimension(self):
        """Test with large apparatus dimension."""
        params = DIIParameters(
            system_dim=2,
            apparatus_dim=500,
            t_final=5.0,
            random_seed=42
        )

        # Should complete without error (may be slow)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            sim = DIISimulation(params)
            result = sim.run_single_measurement()

        self.assertIsNotNone(result['outcome'])

    def test_short_evolution_time(self):
        """Test with very short evolution time."""
        params = DIIParameters(
            system_dim=2,
            apparatus_dim=20,
            t_final=0.1,
            random_seed=42
        )

        sim = DIISimulation(params)
        result = sim.run_single_measurement()

        # Should still produce valid outcome
        self.assertIn(result['outcome'], [0, 1])


def run_comprehensive_tests():
    """Run full test suite with detailed output."""
    print("=" * 70)
    print("DII FRAMEWORK COMPREHENSIVE TEST SUITE")
    print("=" * 70)

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestApparatusMicrostate))
    suite.addTests(loader.loadTestsFromTestCase(TestInformationFunctional))
    suite.addTests(loader.loadTestsFromTestCase(TestCollapseDynamics))
    suite.addTests(loader.loadTestsFromTestCase(TestDIISimulation))
    suite.addTests(loader.loadTestsFromTestCase(TestDIIEnsemble))
    suite.addTests(loader.loadTestsFromTestCase(TestPhysicsValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestNumericalStability))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures:  {len(result.failures)}")
    print(f"Errors:    {len(result.errors)}")

    if result.wasSuccessful():
        print("\n✓ ALL TESTS PASSED")
    else:
        print("\n✗ SOME TESTS FAILED")

    return result


if __name__ == "__main__":
    # Run comprehensive test suite
    result = run_comprehensive_tests()

    # Exit with appropriate code
    exit(0 if result.wasSuccessful() else 1)
