"""
DII Framework Examples and Demonstrations
=========================================

Demonstrates key features and predictions of the DII framework:

1. Single measurement with trajectory visualization
2. Born rule verification with ensemble statistics
3. Apparatus dimension convergence
4. Information functional dynamics
5. Threshold crossing behavior

Run with: python examples_dii.py
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import chi2
import time

from dii_framework import (
    DIIParameters,
    DIISimulation,
    DIIEnsemble,
    ApparatusMicrostate
)


def example_1_single_measurement():
    """
    Example 1: Single measurement with detailed trajectory.

    Shows:
    - System evolution
    - Information functional growth
    - Threshold crossing
    - Collapse dynamics
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Single Measurement Trajectory")
    print("=" * 70)

    # Parameters
    params = DIIParameters(
        system_dim=2,
        apparatus_dim=100,
        coupling_strength=1.0,
        decoherence_rate=0.2,
        collapse_rate=1.0,
        threshold=0.5,
        t_final=50.0,
        dt=0.05,
        random_seed=42
    )

    print("\nParameters:")
    print(f"  System dimension:     {params.system_dim}")
    print(f"  Apparatus dimension:  {params.apparatus_dim}")
    print(f"  Decoherence rate:     {params.decoherence_rate}")
    print(f"  Collapse threshold:   {params.threshold}")

    # Run simulation
    print("\nRunning simulation...")
    start_time = time.time()

    sim = DIISimulation(params)
    result = sim.run_single_measurement()

    elapsed = time.time() - start_time
    print(f"Completed in {elapsed:.2f} seconds")

    # Results
    print("\nResults:")
    print(f"  Outcome:              {result['outcome']}")
    print(f"  System amplitudes:    {result['amplitudes']}")
    print(f"  Apparatus overlaps:   {result['X_overlaps']}")
    print(f"  Selection weights:    {np.abs(result['amplitudes'])**2 * result['X_overlaps']}")

    # Visualize if matplotlib available
    try:
        visualize_trajectory(result)
    except Exception as e:
        print(f"\nVisualization skipped: {e}")


def example_2_born_rule_verification():
    """
    Example 2: Born rule emergence from ensemble statistics.

    Shows that P(outcome k) = |c_k|² emerges from:
    - Typicality over apparatus microstates
    - Deterministic selection rule
    - Large apparatus dimension
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Born Rule Verification")
    print("=" * 70)

    # Parameters
    params = DIIParameters(
        system_dim=2,
        apparatus_dim=100,
        t_final=30.0,
        random_seed=42
    )

    n_trials = 2000

    print(f"\nRunning {n_trials} independent measurements...")
    print("(This may take a minute...)")

    start_time = time.time()

    ensemble = DIIEnsemble(params, n_trials=n_trials)
    stats = ensemble.run_ensemble(verbose=True)

    elapsed = time.time() - start_time
    print(f"\nCompleted in {elapsed:.2f} seconds ({elapsed/n_trials*1000:.1f} ms/trial)")

    # Statistical analysis
    print("\n" + "-" * 70)
    print("STATISTICAL ANALYSIS")
    print("-" * 70)

    print(f"\nEmpirical frequencies: {stats['frequencies']}")
    print(f"Born rule prediction:  {stats['born_rule']}")
    print(f"Statistical error:     ±{stats['statistical_error']}")

    # Chi-squared test
    chi2_stat = stats['chi_squared']
    dof = params.system_dim - 1
    p_value = 1 - chi2.cdf(chi2_stat, df=dof)

    print(f"\nχ² statistic:          {chi2_stat:.3f}")
    print(f"Degrees of freedom:    {dof}")
    print(f"p-value:               {p_value:.3f}")

    if p_value > 0.05:
        print("\n✓ Born rule VERIFIED (p > 0.05)")
        print("  Outcome statistics consistent with |c_i|²")
    else:
        print("\n⚠ Born rule NOT verified (p < 0.05)")
        print("  May need more trials or larger apparatus dimension")

    # Visualize
    try:
        visualize_born_rule(stats, params)
    except Exception as e:
        print(f"\nVisualization skipped: {e}")


def example_3_apparatus_dimension_convergence():
    """
    Example 3: Born rule convergence with apparatus dimension.

    Theoretical prediction:
    - Deviations scale as O(1/√N)
    - Beta(1, N-1) → Exp(1) as N → ∞
    - Born rule becomes exact in large-N limit
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Apparatus Dimension Convergence")
    print("=" * 70)

    dims = [10, 30, 50, 100, 200]
    n_trials = 1000

    print(f"\nTesting apparatus dimensions: {dims}")
    print(f"Trials per dimension: {n_trials}")

    results = []

    for dim in dims:
        print(f"\n--- N = {dim} ---")

        params = DIIParameters(
            system_dim=2,
            apparatus_dim=dim,
            t_final=20.0,
            random_seed=42
        )

        ensemble = DIIEnsemble(params, n_trials=n_trials)
        stats = ensemble.run_ensemble(verbose=False)

        # Compute deviation
        deviation = np.max(np.abs(stats['frequencies'] - stats['born_rule']))

        results.append({
            'dim': dim,
            'frequencies': stats['frequencies'],
            'deviation': deviation,
            'chi2': stats['chi_squared']
        })

        print(f"  Frequencies:  {stats['frequencies']}")
        print(f"  Deviation:    {deviation:.4f}")
        print(f"  Expected:     ~{1/np.sqrt(dim):.4f} (scaling estimate)")

    # Summary
    print("\n" + "-" * 70)
    print("CONVERGENCE SUMMARY")
    print("-" * 70)
    print(f"{'Dimension':<12} {'Deviation':<15} {'Expected O(1/√N)':<20} {'χ²':<10}")
    print("-" * 70)

    for r in results:
        expected = 1 / np.sqrt(r['dim'])
        print(f"{r['dim']:<12} {r['deviation']:<15.4f} {expected:<20.4f} {r['chi2']:<10.2f}")

    # Visualize
    try:
        visualize_convergence(results)
    except Exception as e:
        print(f"\nVisualization skipped: {e}")


def example_4_information_dynamics():
    """
    Example 4: Information functional dynamics.

    Shows how information about each outcome:
    - Starts near zero (superposition)
    - Grows during decoherence
    - One channel "wins" (crosses threshold)
    - Collapse amplifies winner
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Information Functional Dynamics")
    print("=" * 70)

    params = DIIParameters(
        system_dim=2,
        apparatus_dim=80,
        decoherence_rate=0.15,
        collapse_rate=2.0,
        threshold=0.4,
        t_final=60.0,
        dt=0.1,
        random_seed=123
    )

    print("\nRunning simulation to track information flow...")

    sim = DIISimulation(params)
    result = sim.run_single_measurement()

    # Extract information history
    info_history = result['info_history']

    if not info_history:
        print("No information history recorded.")
        return

    times = np.array([t for t, _ in info_history])
    info_0 = np.array([info[0] for _, info in info_history])
    info_1 = np.array([info[1] for _, info in info_history])
    info_gap = np.abs(info_0 - info_1)

    print(f"\nFinal outcome: {result['outcome']}")
    print(f"Initial info:  I_0={info_0[0]:.3f}, I_1={info_1[0]:.3f}")
    print(f"Final info:    I_0={info_0[-1]:.3f}, I_1={info_1[-1]:.3f}")
    print(f"Final gap:     ΔI={info_gap[-1]:.3f} (threshold: {params.threshold})")

    # Find threshold crossing time
    threshold_crossed = info_gap > params.threshold
    if np.any(threshold_crossed):
        t_cross = times[threshold_crossed][0]
        print(f"Threshold crossed at t ≈ {t_cross:.1f}")

    # Visualize
    try:
        visualize_information_dynamics(times, info_0, info_1, params.threshold)
    except Exception as e:
        print(f"\nVisualization skipped: {e}")


def example_5_apparatus_microstate_distribution():
    """
    Example 5: Apparatus microstate overlap distribution.

    Verifies Porter-Thomas statistics:
    - Sample many apparatus microstates
    - Compute overlaps X_i = |⟨A_i|ψ_A⟩|²
    - Check distribution against Exp(1)
    """
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Apparatus Microstate Distribution")
    print("=" * 70)

    dim = 100
    n_samples = 5000

    print(f"\nApparatus dimension: {dim}")
    print(f"Number of samples:   {n_samples}")
    print("\nSampling apparatus microstates...")

    overlaps_all = []

    for i in range(n_samples):
        apparatus = ApparatusMicrostate(dim, seed=None)
        apparatus.sample_thermal_state()

        # Fixed pointer state (basis vector)
        pointer = np.eye(dim)[0]
        overlap = np.abs(np.vdot(pointer, apparatus.state))**2

        # Rescale by dimension for Exp(1)
        overlaps_all.append(overlap * dim)

        if (i + 1) % 1000 == 0:
            print(f"  {i + 1}/{n_samples} samples")

    overlaps_all = np.array(overlaps_all)

    # Statistical test
    from scipy.stats import kstest

    ks_stat, p_value = kstest(overlaps_all, 'expon', args=(0, 1))

    print("\n" + "-" * 70)
    print("PORTER-THOMAS STATISTICS")
    print("-" * 70)
    print(f"Mean (expected 1.0):  {np.mean(overlaps_all):.3f}")
    print(f"Std  (expected 1.0):  {np.std(overlaps_all):.3f}")
    print(f"\nKolmogorov-Smirnov test vs Exp(1):")
    print(f"  KS statistic:       {ks_stat:.4f}")
    print(f"  p-value:            {p_value:.3f}")

    if p_value > 0.05:
        print("\n✓ Overlaps follow exponential distribution (p > 0.05)")
        print("  Porter-Thomas statistics VERIFIED")
    else:
        print("\n⚠ Exponential hypothesis rejected (p < 0.05)")
        print("  May need larger apparatus dimension")

    # Visualize
    try:
        visualize_overlap_distribution(overlaps_all)
    except Exception as e:
        print(f"\nVisualization skipped: {e}")


# ============================================================================
# VISUALIZATION FUNCTIONS
# ============================================================================

def visualize_trajectory(result):
    """Visualize single measurement trajectory."""
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle("Single Measurement Trajectory", fontsize=14, fontweight='bold')

    times = result['times']
    info_history = result['info_history']

    if not info_history:
        print("No trajectory data to visualize")
        return

    info_times = np.array([t for t, _ in info_history])
    info_0 = np.array([info[0] for _, info in info_history])
    info_1 = np.array([info[1] for _, info in info_history])

    # Plot 1: Information functionals
    axes[0, 0].plot(info_times, info_0, label='I₀(t)', linewidth=2)
    axes[0, 0].plot(info_times, info_1, label='I₁(t)', linewidth=2)
    axes[0, 0].set_xlabel('Time')
    axes[0, 0].set_ylabel('Information I_k')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].set_title('Information Functional Dynamics')

    # Plot 2: Information gap
    gap = np.abs(info_0 - info_1)
    axes[0, 1].plot(info_times, gap, color='purple', linewidth=2)
    axes[0, 1].axhline(0.5, color='red', linestyle='--', label='Threshold')
    axes[0, 1].set_xlabel('Time')
    axes[0, 1].set_ylabel('ΔI = |I₀ - I₁|')
    axes[0, 1].legend()
    axes[0, 1].grid(True, alpha=0.3)
    axes[0, 1].set_title('Information Gap')

    # Plot 3: Collapse functional
    F_values = np.tanh(gap / 0.5)
    axes[1, 0].plot(info_times, F_values, color='orange', linewidth=2)
    axes[1, 0].set_xlabel('Time')
    axes[1, 0].set_ylabel('F(ΔI) = tanh(ΔI/Δ_crit)')
    axes[1, 0].grid(True, alpha=0.3)
    axes[1, 0].set_title('Collapse Functional')

    # Plot 4: Outcome summary
    outcome = result['outcome']
    amplitudes = result['amplitudes']
    overlaps = result['X_overlaps']

    axes[1, 1].bar(['Outcome 0', 'Outcome 1'],
                   np.abs(amplitudes)**2 * overlaps,
                   color=['blue' if i == outcome else 'lightblue' for i in range(2)])
    axes[1, 1].set_ylabel('|c_i|² X_i (selection weight)')
    axes[1, 1].set_title(f'Outcome Selection (Result: {outcome})')
    axes[1, 1].grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig('dii_single_measurement.png', dpi=150)
    print("\nTrajectory plot saved: dii_single_measurement.png")
    plt.close()


def visualize_born_rule(stats, params):
    """Visualize Born rule verification."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle('Born Rule Verification', fontsize=14, fontweight='bold')

    # Plot 1: Frequencies
    outcomes = range(params.system_dim)
    width = 0.35

    axes[0].bar(np.array(outcomes) - width/2, stats['frequencies'],
                width, label='Empirical', color='steelblue')
    axes[0].bar(np.array(outcomes) + width/2, stats['born_rule'],
                width, label='Born Rule', color='orange')
    axes[0].errorbar(outcomes, stats['frequencies'], yerr=stats['statistical_error'],
                     fmt='none', color='black', capsize=5)
    axes[0].set_xlabel('Outcome')
    axes[0].set_ylabel('Frequency')
    axes[0].set_title(f'Frequencies (N={stats["n_trials"]} trials)')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3, axis='y')

    # Plot 2: Outcome distribution
    axes[1].hist(stats['outcomes'], bins=params.system_dim, density=True,
                 alpha=0.7, color='steelblue', edgecolor='black')
    axes[1].axhline(1/params.system_dim, color='orange', linestyle='--',
                    linewidth=2, label='Born Rule')
    axes[1].set_xlabel('Outcome')
    axes[1].set_ylabel('Probability Density')
    axes[1].set_title('Outcome Distribution')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig('dii_born_rule.png', dpi=150)
    print("\nBorn rule plot saved: dii_born_rule.png")
    plt.close()


def visualize_convergence(results):
    """Visualize apparatus dimension convergence."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle('Apparatus Dimension Convergence', fontsize=14, fontweight='bold')

    dims = [r['dim'] for r in results]
    deviations = [r['deviation'] for r in results]
    chi2_values = [r['chi2'] for r in results]

    # Plot 1: Deviation vs dimension
    axes[0].plot(dims, deviations, 'o-', linewidth=2, markersize=8,
                 label='Empirical', color='steelblue')

    # Theoretical O(1/√N) scaling
    dims_theory = np.linspace(min(dims), max(dims), 100)
    scaling_theory = 1 / np.sqrt(dims_theory)
    axes[0].plot(dims_theory, scaling_theory, '--', linewidth=2,
                 label='O(1/√N) scaling', color='orange')

    axes[0].set_xlabel('Apparatus Dimension N')
    axes[0].set_ylabel('Max Deviation from Born Rule')
    axes[0].set_xscale('log')
    axes[0].set_yscale('log')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3, which='both')
    axes[0].set_title('Convergence Rate')

    # Plot 2: χ² statistic
    axes[1].plot(dims, chi2_values, 'o-', linewidth=2, markersize=8,
                 color='purple')
    axes[1].axhline(1.0, color='red', linestyle='--', label='Expected (dof=1)')
    axes[1].set_xlabel('Apparatus Dimension N')
    axes[1].set_ylabel('χ² Statistic')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    axes[1].set_title('Statistical Fit Quality')

    plt.tight_layout()
    plt.savefig('dii_convergence.png', dpi=150)
    print("\nConvergence plot saved: dii_convergence.png")
    plt.close()


def visualize_information_dynamics(times, info_0, info_1, threshold):
    """Visualize information functional dynamics."""
    fig, axes = plt.subplots(2, 1, figsize=(10, 8))
    fig.suptitle('Information Functional Dynamics', fontsize=14, fontweight='bold')

    # Plot 1: Information functionals
    axes[0].plot(times, info_0, label='I₀(t)', linewidth=2, color='blue')
    axes[0].plot(times, info_1, label='I₁(t)', linewidth=2, color='red')
    axes[0].set_xlabel('Time')
    axes[0].set_ylabel('Information I_k(t)')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    axes[0].set_title('Information Integration for Each Outcome')

    # Plot 2: Gap and threshold
    gap = np.abs(info_0 - info_1)
    axes[1].plot(times, gap, linewidth=2, color='purple', label='ΔI(t)')
    axes[1].axhline(threshold, color='red', linestyle='--', linewidth=2,
                    label=f'Threshold (Δ_crit={threshold})')
    axes[1].fill_between(times, 0, threshold, alpha=0.2, color='red',
                          label='Pre-collapse region')
    axes[1].set_xlabel('Time')
    axes[1].set_ylabel('Information Gap ΔI')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    axes[1].set_title('Threshold Crossing')

    plt.tight_layout()
    plt.savefig('dii_information_dynamics.png', dpi=150)
    print("\nInformation dynamics plot saved: dii_information_dynamics.png")
    plt.close()


def visualize_overlap_distribution(overlaps):
    """Visualize apparatus microstate overlap distribution."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle('Porter-Thomas Distribution Verification', fontsize=14, fontweight='bold')

    # Plot 1: Histogram
    axes[0].hist(overlaps, bins=50, density=True, alpha=0.7,
                 color='steelblue', edgecolor='black', label='Empirical')

    # Theoretical Exp(1)
    x = np.linspace(0, np.max(overlaps), 200)
    axes[0].plot(x, np.exp(-x), 'r--', linewidth=2, label='Exp(1)')
    axes[0].set_xlabel('Rescaled Overlap (N × X_i)')
    axes[0].set_ylabel('Probability Density')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    axes[0].set_title('Overlap Distribution')

    # Plot 2: Q-Q plot
    from scipy.stats import probplot

    probplot(overlaps, dist='expon', plot=axes[1])
    axes[1].set_title('Q-Q Plot vs Exponential')
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('dii_porter_thomas.png', dpi=150)
    print("\nPorter-Thomas plot saved: dii_porter_thomas.png")
    plt.close()


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run all examples."""
    print("=" * 70)
    print("DII FRAMEWORK - COMPREHENSIVE EXAMPLES")
    print("=" * 70)
    print("\nThese examples demonstrate:")
    print("1. Single measurement dynamics")
    print("2. Born rule emergence from typicality")
    print("3. Convergence with apparatus dimension")
    print("4. Information functional dynamics")
    print("5. Porter-Thomas statistics")
    print("\nNote: Some examples may take a few minutes.")
    print("=" * 70)

    try:
        # Run examples
        example_1_single_measurement()
        example_2_born_rule_verification()
        example_3_apparatus_dimension_convergence()
        example_4_information_dynamics()
        example_5_apparatus_microstate_distribution()

        print("\n" + "=" * 70)
        print("ALL EXAMPLES COMPLETED")
        print("=" * 70)
        print("\nPlots saved:")
        print("  - dii_single_measurement.png")
        print("  - dii_born_rule.png")
        print("  - dii_convergence.png")
        print("  - dii_information_dynamics.png")
        print("  - dii_porter_thomas.png")

    except KeyboardInterrupt:
        print("\n\nExamples interrupted by user.")
    except Exception as e:
        print(f"\n\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
