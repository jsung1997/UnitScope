* Example: Diff pair + mirror bias with extra loads

* Differential pair
M1 n1 vinp ntail 0 NMOS
M2 n2 vinn ntail 0 NMOS

* Simple current mirror (PMOS) providing bias
M3 nref nref vdd vdd PMOS   * diode-connected (G=D=nref)
M4 nbias nref vdd vdd PMOS  * mirror output, shares gate/source with M3

* Use that bias net to bias other devices (creates dependencies)
M5 n3 nbias vdd vdd PMOS
M6 n4 nbias vdd vdd PMOS
M7 n5 nbias vdd vdd PMOS

* Passives (ignored for unit detection right now, but parsed)
R1 n1 vdd 10k
C1 n2 0 1p
