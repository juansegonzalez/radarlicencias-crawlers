# License code prefixes for Mallorca (Consejo + known variants). Longest first so ETVPL matches before ETV.
# Regenerate from census: python scripts/build_license_patterns.py data/consejo_*.jl

LICENSE_CODE = r"(?:ETV60[/\-\s]*\d+|ETVPL[/\-\s]*\d+|GTOIB[/\-\s]*\d+|SBAL[/\-\s]*\d+|AVBAL[/\-\s]*\d+|CTE[/\-\s]*\d+|ABT[/\-\s]*\d+|CTL[/\-\s]*\d+|CTC[/\-\s]*\d+|ETV[/\-\s]*\d+|CR[/\-\s]*\d+|BC[/\-\s]*\d+|SF[/\-\s]*\d+|TA[/\-\s]*\d+|AT[/\-\s]*\d+|EE[/\-\s]*\d+|MT[/\-\s]*\d+|CT[/\-\s]*\d+|CP[/\-\s]*\d+|CC[/\-\s]*\d+|TI[/\-\s]*\d+|AG[/\-\s]*\d+|GT[/\-\s]*\d+|EH[/\-\s]*\d+|CE[/\-\s]*\d+|CA[/\-\s]*\d+|ETR[/\-\s]*\d+|HO[/\-\s]*\d+|HR[/\-\s]*\d+|HA[/\-\s]*\d+|SB[/\-\s]*\d+|OC[/\-\s]*\d+|TC[/\-\s]*\d+|VT[/\-\s]*\d+|BCP[/\-\s]*\d+|D[/\-\s]*\d+|R[/\-\s]*\d+|H[/\-\s]*\d+|C[/\-\s]*\d+|B[/\-\s]*\d+)"
