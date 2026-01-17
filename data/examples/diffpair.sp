* Simple differential pair example
M1 n1 vinp ntail 0 NMOS
M2 n2 vinn ntail 0 NMOS

* Other devices (noise for the detector)
M3 n3 vbias vdd vdd PMOS
R1 n1 vdd 10k
C1 n2 0 1p