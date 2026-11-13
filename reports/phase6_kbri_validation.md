# Phase 6: KBRI v1.0 validation

Company-months scored: 18036; value-chain basket 2010-10-29 to 2026-10-30; disclosure basket 2024-01-31 to 2026-10-30.

| Check | Result |
| --- | --- |
| Weights: equal weights | company bands agree 91.3% (r=0.982); value-chain basket bands agree 100.0% (r=0.955) |
| Weights: valuation-heavy (40%) | company bands agree 82.9% (r=0.948); value-chain basket bands agree 99.5% (r=0.928) |
| KBRI-abs vs KBRI-rel (company) | bands agree 79.5%, r=0.907 |
| Ablation (company KBRI correlation without component) | valuation r=0.811; quality r=0.946; capex r=0.891; financing r=0.968; speculative r=0.986 |
| Reverse DCF: terminal growth 2% | median g* shift +1.3 pts; company bands agree 99.3%; value-chain basket r=0.998; latest company rank correlation 1.000 |
| Reverse DCF: terminal growth 4% | median g* shift -1.6 pts; company bands agree 98.8%; value-chain basket r=0.996; latest company rank correlation 1.000 |
| Reverse DCF: margin -5 points | median g* shift +3.6 pts; company bands agree 96.2%; value-chain basket r=0.987; latest company rank correlation 0.995 |
| Reverse DCF: margin +5 points | median g* shift -2.9 pts; company bands agree 96.5%; value-chain basket r=0.997; latest company rank correlation 0.997 |
| Reverse DCF: Damodaran implied ERP | median g* shift +0.2 pts; company bands agree 97.2%; value-chain basket r=0.962; latest company rank correlation 0.999 |
| Survivorship (value-chain basket, end members only) | firms that left at some point and are excluded: ['AAOI', 'ALGM', 'AMKR', 'APLD', 'APPF', 'ASAN', 'BILL', 'CLVT', 'DBX', 'DOCS', 'DUOL', 'DXC', 'ENPH', 'EPAM', 'GDRX', 'GTLB', 'GTM', 'KD', 'KVYO', 'MTCH', 'OTEX', 'PATH', 'PCTY', 'PEGA', 'PPLI', 'PSN', 'RMBS', 'RNG', 'SANM', 'SEDG', 'SNAP', 'TDC', 'TTD', 'TTMI', 'VIAV']; bands agree 100.0%, r=0.991 |

Independent recalculation: see src/kbri/recalc_numpy.py (g* to 2.5e-11; company scores and basket mean exact).
