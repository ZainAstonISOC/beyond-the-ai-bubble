# Phase 6: KBRI v1.0 validation

Company-months scored: 3352; value-chain basket 2011-05-31 to 2026-10-30; disclosure basket 2024-01-31 to 2026-10-30.

| Check | Result |
| --- | --- |
| Weights: equal weights | company bands agree 90.5% (r=0.983); value-chain basket bands agree 100.0% (r=0.953) |
| Weights: valuation-heavy (40%) | company bands agree 84.0% (r=0.967); value-chain basket bands agree 98.4% (r=0.948) |
| KBRI-abs vs KBRI-rel (company) | bands agree 65.5%, r=0.801 |
| Ablation (company KBRI correlation without component) | valuation r=0.851; quality r=0.958; capex r=0.904; financing r=0.966; speculative r=0.987 |
| Reverse DCF: terminal growth 2% | median g* shift +1.3 pts; company bands agree 99.2%; value-chain basket r=0.999; latest company rank correlation 0.999 |
| Reverse DCF: terminal growth 4% | median g* shift -1.5 pts; company bands agree 98.8%; value-chain basket r=0.997; latest company rank correlation 0.999 |
| Reverse DCF: margin -5 points | median g* shift +2.9 pts; company bands agree 97.6%; value-chain basket r=0.973; latest company rank correlation 0.997 |
| Reverse DCF: margin +5 points | median g* shift -2.4 pts; company bands agree 98.4%; value-chain basket r=0.999; latest company rank correlation 0.999 |
| Reverse DCF: Damodaran implied ERP | median g* shift +0.4 pts; company bands agree 97.1%; value-chain basket r=0.977; latest company rank correlation 0.998 |
| Survivorship (value-chain basket, end members only) | firms that left at some point and are excluded: none; bands agree 100.0%, r=1.000 |

Independent recalculation: see src/kbri/recalc_numpy.py (g* to 2.5e-11; company scores and basket mean exact).
