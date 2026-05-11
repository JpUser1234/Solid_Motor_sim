# Especificación de Entradas y Salidas — J850 Motor Sólido v4
> Documento para integración con Copilot / repositorio de código  
> Basado en análisis de fórmulas vs. valores hardcodeados del archivo `J850_v4.xlsx`

---

## Convención

| Tipo | Significado |
|---|---|
| **INPUT directo** | Celda con valor literal — el usuario lo escribe |
| **INPUT constante** | Valor físico fijo (no cambia entre diseños) |
| **OUTPUT calculado** | Celda con fórmula — se deriva de otras celdas |
| **OUTPUT referenciado** | Fórmula que jala de otra hoja |

---

## MÓDULO 1 — `Diseño` (Hoja principal de diseño)

### 1.1 Inputs directos del usuario (lo que el ingeniero introduce)

```
Categoría: Geometría del tubo
  DEXT       = 0.0521 m         → Diámetro externo del tubo
  Esp        = 0.0016 m         → Espesor de pared del tubo
  [Material]  = "Aluminio"      → Texto descriptivo (no numérico)
  [Aleación]  = "6061-T6"       → Texto descriptivo

Categoría: Propiedades mecánicas del material (tubo)
  E          = 69 GPa           → Módulo de elasticidad (hardcodeado como =69000*10^6)
  σY         = 275 MPa          → Esfuerzo de cedencia en tensión
  τU         = 205 MPa          → Esfuerzo último en cortante
  σU         = 310 MPa          → Esfuerzo último en tensión
  [τY]       = vacío            → Esfuerzo de cedencia en cortante (no definido en diseño actual)

Categoría: Condiciones de cámara
  P1         = 1000 psi         → Presión de diseño de la cámara
  T1         = 1720 K           → Temperatura adiabática de la llama

Categoría: Geometría de los granos (BATES)
  ng         = 4                → Número de granos
  ri         = 0.010 m          → Radio interno inicial del grano
  Lg         = 0.070 m          → Longitud de cada grano
  Sg         = 0.002 m          → Separación axial entre granos

Categoría: Propiedades del propelente
  a          = 0.0665           → Constante de tasa de quemado (ley de Vieille, unidades PSI)
  n          = 0.319            → Exponente de presión de la ley de Vieille
  ρP         = 1776.25 kg/m³    → Densidad del propelente

Categoría: Propiedades termodinámicas de los gases
  k (γ)      = 1.044            → Razón de calores específicos (Cp/Cv)
  R          = 195.71 J/kg·K   → Constante específica del gas de combustión

Categoría: Tobera cónica
  α          = 12°              → Ángulo de la sección divergente
  β          = 30°              → Ángulo de la sección convergente
  ηnozzle    = 0.85             → Eficiencia de la tobera
  Lint_med   = 3 mm             → Longitud de sección intermedia (fija)

Categoría: Tornillos (tapas)
  NTornillo  = 8                → Número de tornillos
  DTornillo  = 0.005 m          → Diámetro del tornillo
  DistT-P    = 0.012 m          → Distancia del centro del tornillo a la pared

Categoría: Tornillos — propiedades mecánicas (Acero)
  NNúcleo    = 0.0038 m         → Diámetro de núcleo del tornillo
  σY_torn    = 250 MPa          → Fluencia en tensión del tornillo
  τY_torn    = 145 MPa          → Fluencia en cortante del tornillo
  σU_torn    = 400 MPa          → Último en tensión del tornillo
```

### 1.2 Inputs constantes físicas (no cambian entre diseños)

```
Patm       = 101325 Pa         → Presión atmosférica
vs         = 343.59 m/s        → Velocidad del sonido ambiente
g          = 9.81 m/s²         → Aceleración gravitacional estándar
```

### 1.3 Outputs calculados intermedios

```
Geometría del tubo:
  RINT       = (DEXT - 2·Esp) / 2                     → Radio interno del tubo
  re         = RINT - 0.002                            → Radio externo del grano (clearance de 2 mm)

Granos:
  Vg         = π · Lg · (re² - ri²)                  → Volumen unitario del grano
  mg         = ρP · Vg                                → Masa de un grano [g]
  LT         = ng · Lg                                → Longitud total de la sección de combustible
  L          = (ng-1)·Sg + ng·Lg                      → Longitud total incluyendo separaciones
  Ap         = π · ri²                                → Port area (área del canal central)

Propelente:
  br         = (a · (P1_psi ^ n)) · 0.0254            → Tasa de quemado [m/s] (conversión in/s → m/s)
  Vp         = π · Lg · ng · (re² - ri²)             → Volumen total de propelente
  mp         = ρP · Vp                                → Masa total de propelente [kg]
  TQ         = (re - ri) / br                         → Tiempo de quemado [s]
  Ab         = referenciado de hoja "Coport. de Area" → Área de quemado promedio [m²]
  ṁ          = Ab · ρP · br                           → Flujo másico de combustión [kg/s]

Termodinámica isentrópica:
  P1_Pa      = P1 · 6894.757                          → Presión en Pascales
  V1         = R·T1 / P1_Pa                           → Volumen específico en cámara [m³/kg]
  Vt         = V1 · ((k+1)/2)^(1/(k-1))              → Volumen específico en garganta
  Pt         = P1_Pa · (V1/Vt)^k                      → Presión en garganta [Pa]
  P2         = Patm                                   → Presión de salida = atmosférica
  V2         = V1 · (P1_Pa/P2)^(1/k)                 → Volumen específico en escape
  Tt         = T1 · (V1/Vt)^(k-1)                    → Temperatura en garganta [K]
  T2         = T1 · (P2/P1_Pa)^((k-1)/k)             → Temperatura en escape [K]
  vt         = sqrt((2k/(k+1)) · R · T1)             → Velocidad en garganta [m/s]
  at         = sqrt(k · R · Tt)                      → Velocidad sónica local en garganta
  Mt         = vt / at                               → Número de Mach en garganta (≈1.0)
  v2         = sqrt((2k/(k-1)) · R · T1 · (1-(P2/P1)^((k-1)/k)))  → Velocidad de escape [m/s]
  a2         = sqrt(k · R · T2)                      → Velocidad sónica local en escape
  M2         = v2 / a2                               → Número de Mach de escape (~2.97)
  c*         = sqrt(R·T1 / (k·(2/(k+1))^((k+1)/(k-1))))  → Velocidad característica [m/s]

Tobera (áreas y dimensiones):
  At         = ṁ · Vt / vt                           → Área de garganta [m²]
  A2         = ṁ · V2 / v2                           → Área de salida [m²]
  ε          = A2 / At                               → Coeficiente de expansión de área
  rt         = sqrt(At·10⁴ / π)                      → Radio de garganta [cm]
  r2         = sqrt(A2·10⁴ / π)                      → Radio de salida [cm]
  LD         = (r2 - rt) / tan(α)                    → Longitud sección divergente [cm]
  h          = RINT·100 - rt                         → Altura sección convergente [cm]
  LC         = h / tan(β)                            → Longitud sección convergente [cm]
  Lnozzle    = LD + LC + Lint_med·0.1                → Longitud total de tobera [cm]

Performance:
  CF         = sqrt((2k²/(k-1)) · (2/(k+1))^((k+1)/(k-1)) · (1-(P2/P1)^((k-1)/k))) + (P2-Patm)·A2/(At·P1)
  F_teo      = ṁ · v2                                → Empuje teórico [N]
  F_esp      = PROMEDIO de F(t) del simulador (>0)   → Empuje promedio esperado [N]
  F_max      = MAX de F(t) del simulador             → Empuje máximo [N]
  Isp_teo    = v2 / 9.81                             → Impulso específico teórico [s]
  Isp_esp    = referenciado del simulador             → Impulso específico esperado [s]
  IT_teo     = F_teo · TQ                            → Impulso total teórico [N·s]
  IT_esp     = referenciado del simulador             → Impulso total esperado [N·s]
  Kn         = Ab / At                               → Razón de áreas Kn promedio
  ψ          = Ap / At                               → Port-to-Throat ratio
  φ          = LT / (2·re)                           → L/D del motor
  CD         = 1 / c*                                → Coeficiente de descarga [s/m]
  Clase      = LOOKUP(IT_esp, tabla A-Q)             → Clasificación NAR/Tripoli

Resistencia estructural del tubo:
  PMAX       = MAX(P_camara(t)) del simulador        → Presión máxima registrada [Pa]
  Dm         = DEXT - Esp                            → Diámetro medio del tubo
  CEsp       = Dm / Esp                              → Condición de pared delgada (>20 = delgado)
  σ1         = PMAX·RINT / Esp          (pared delgada)  → Esfuerzo tangencial (hoop) [Pa]
  σ2         = PMAX·RINT / (2·Esp)     (pared delgada)  → Esfuerzo longitudinal [Pa]
  σ3         = 0                        (pared delgada)  → Esfuerzo radial [Pa]
  σMAX       = MAX(σ1, σ2, σ3)                       → Esfuerzo máximo [Pa]
  η_tubo     = σY / σMAX                             → Margen de seguridad del tubo

Tornillos y tapas:
  ATubo      = π·((DEXT/2)² - RINT²)                → Área transversal anular del tubo [m²]
  θ          = DEGREES(ASIN(DTornillo/2 / RINT))     → Ángulo de sector por tornillo [°]
  ATornillo  = (θ_rad/2)·((DEXT/2)² - RINT² - Esp²) → Área transversal de 1 tornillo [m²]
  ATornillos = ATornillo · NTornillo                 → Área total ocupada por tornillos [m²]
  AMaterial  = ATubo - ATornillos                    → Área neta de material [m²]
  EspCortante= DistT-P - DTornillo/2                → Espesor del segmento cortante [m]
  ATapa      = π · RINT²                             → Área interna de la tapa [m²]
  FTapa      = PMAX · ATapa                          → Fuerza máxima sobre tapa [N]
  FTornillo  = FTapa / NTornillo                     → Fuerza por tornillo [N]
  σ_circ     = FTapa / AMaterial                     → Tensión circunferencial [Pa]
  η_tensión  = σY / σ_circ                           → Margen de seguridad en tensión
  ACortante  = EspCortante · Esp                     → Área de cortante por tornillo [m²]
  τ_prom     = FTornillo / ACortante                 → Cortante promedio [Pa]
  η_cortante = τU / τ_prom                           → Margen de seguridad en cortante
  σb         = FTornillo / ATornillo                 → Esfuerzo de aplastamiento [Pa]
  η_aplast   = σY / σb                               → Margen de seguridad en aplastamiento

Deformación del tubo:
  ε1         = σ1 / E                                → Deformación unitaria circunferencial
  δ1         = ε1 · (2π·RINT) · 1000                → Deformación circunf. interna [mm]
  δExt       = ε1 · (π·DEXT) · 1000                 → Deformación circunf. externa [mm]
  RINT_fin   = RINT + δ1/1000/(2π)                  → Radio interno final [m]
  ΔRINT      = (RINT_fin - RINT) · 1000              → Incremento de radio interno [mm]
  REXT_fin   = (π·DEXT + δExt/1000)/(2π)            → Radio externo final [m]
  ΔREXT      = (REXT_fin - DEXT/2) · 1000            → Incremento de radio externo [mm]

Tornillos — resistencia:
  ANúcleo    = π · (NNúcleo/2)²                     → Área de núcleo del tornillo [m²]
  τ_torn     = FTornillo / ANúcleo                   → Esfuerzo cortante en tornillo [Pa]
  η_torn_c   = τY_torn / τ_torn                      → Margen de seguridad del tornillo
```

---

## MÓDULO 2 — `Coport. de Area` (Comportamiento del área de quemado)

### 2.1 Inputs (todos referenciados de Diseño)

```
Re_G   = Diseño.re         → Radio externo del grano [m]
Lg     = Diseño.Lg         → Longitud del grano [m]
RI     = Diseño.ri         → Radio interno inicial [m]
br     = Diseño.br         → Tasa de quemado [m/s]
TQ     = Diseño.TQ         → Tiempo de quemado [s]
N_pasos= 1000              → Subdivisiones temporales (hardcodeado)
```

### 2.2 Lógica por cada fila (paso de tiempo i)

```
Δt         = TQ / 1000                          → Paso de tiempo [s]
t[i]       = i · Δt                             → Tiempo [s]
Rinst[i]   = RI + br · t[i]                    → Radio instantáneo [m]
Linst[i]   = Lg - 2 · br · t[i]               → Longitud instantánea (tapas se queman) [m]
Atrans[i]  = π · Rinst[i]²                    → Área transversal del grano [m²]
Along[i]   = 2π · Rinst[i] · Linst[i]        → Área lateral longitudinal [m²]
Ab[i]      = Atrans[i] + Along[i]             → Área de quemado por grano [m²]
ΔAb[i]    = Ab[i] - Ab[i-1]                   → Diferencia de área entre pasos
```

### 2.3 Outputs de la hoja

```
Ab_prom    = PROMEDIO(Ab[0..1000])             → Área de quemado promedio [m²]
σ_Ab       = DESVESTP(Ab[0..1000]) · 10⁴      → Desviación estándar del área de quemado
             (Este valor se muestra en Diseño como indicador de progresividad)
Ab_final   = Ab[1000]                          → Área en el último paso (referenciada por Diseño)
```

> **Nota de progresividad:** Si `ΔAb > 0` el grano es progresivo (área crece), `= 0` es neutro, `< 0` es regresivo.

---

## MÓDULO 3 — `Comportamiento en el Tiempo` (Balística interna)

### 3.1 Inputs (todos referenciados de Diseño)

```
Patm      → Presión atmosférica [Pa]
a, n      → Constantes de tasa de quemado
ρP        → Densidad del propelente [kg/m³]
Re_G, Lg, ri, ng  → Geometría del grano
At        → Área de garganta [m²]
A2        → Área de salida [m²]
ηnozzle   → Eficiencia de tobera
M2        → Mach de escape
TQ        → Tiempo de quemado [s]
c*        → Velocidad característica [m/s]
Vtotal    → Volumen interno total del motor [m³] (= π·RINT²·L)
T1, k, R  → Propiedades termodinámicas
```

### 3.2 Variables calculadas por cada paso de tiempo i (columnas de la tabla)

```
COLUMNA  SÍMBOLO       FÓRMULA / LÓGICA
t        t             tiempo acumulado [s]
Δt       Δt            paso de tiempo = TQ/1000 [s]
PC-abs   Pc            presión de cámara absoluta [Pa]  ← resultado de balance másico iterativo
PC       Pc_psi        Pc / 6894.757 [psi]
PC-abs*  Pc_man        Pc - Patm [Pa] (presión manométrica)
br       br(t)         = a · (Pc_psi ^ n) · 0.0254 [m/s]
Rinst    R(t)          = ri + br·t [m]
Linst    L(t)          = Lg - 2·br·t [m]
Atrans   Atrans(t)     = π·R(t)² [m²]
Along    Along(t)      = 2π·R(t)·L(t) [m²]
Ab       Ab(t)         = Atrans + Along [m²] (por grano)
Ab-T     Ab_total(t)   = ng · Ab(t) [m²] (área total de quemado)
VT       Vp(t)         = π·L(t)·(re²-R(t)²)·ng [m³] (volumen de propelente)
MT       mp(t)         = ρP · Vp(t) [kg] (masa de propelente restante)
MG       mG(t)         = mp(0) - mp(t) [kg] (masa de propelente quemada)
m'prod   ṁ_prod(t)    = ρP · br · Ab_total [kg/s] (flujo másico producido)
M'escp   ṁ_escp(t)   = Pc · At / c* [kg/s] (flujo másico que escapa por garganta)
Δm       Δm(t)         = ṁ_prod - ṁ_escp [kg/s] (balance de masa)
ΔmEsc    Δm_esc(t)    = ṁ_escp · Δt [kg] (masa que escapa en un paso)
Mi       m_interna(t)  = masa acumulada de gas dentro de la cámara [kg]
VL       VL(t)         = Vtotal - Vp(t) [m³] (volumen libre en cámara)
Kn       Kn(t)         = Ab_total / At [-] (razón de áreas)
Pe       Pe_virt(t)    = presión de salida virtual calculada por expansión isentrópica
P2       P2(t)         = Pc · (1 + (k-1)/2 · M2²)^(-k/(k-1)) [Pa] → presión real de salida
CF       CF(t)         = coeficiente de empuje teórico
CF_adj   CF_adj(t)     = CF · ηnozzle → coeficiente ajustado por eficiencia
F        F(t)          = CF_adj · At · Pc [N] → empuje instantáneo
IT       IT(t)         = Σ F(t) · Δt [N·s] → impulso acumulado
F_kgf    F(t)/9.81     [kgf]
```

### 3.3 Outputs finales de la hoja (celdas de resumen)

```
IT_esp    = IT total acumulado al fin del quemado [N·s]  → jalado por Diseño.E84
Isp_esp   = IT_esp / (mp_total · 9.81) [s]              → jalado por Diseño.E82
Pmax      = MAX(Pc(t))  [Pa]                             → jalado por Diseño para análisis estructural
F_prom    = PROMEDIO(F(t) > 0) [N]                       → jalado por Diseño.E76
F_max     = MAX(F(t)) [N]                                → jalado por Diseño.E78
```

---

## MÓDULO 4 — `Simulador de Altitud` (Trayectoria 1D)

### 4.1 Inputs directos del usuario (únicos a esta hoja)

```
HInic     = 100 m          → Altitud de lanzamiento sobre el nivel del mar
ϕ         = 9.9361°        → Latitud geográfica (decimal) — afecta g local
mMotor    = 1.00 kg        → Masa del motor (estructura, sin propelente)
mFuselaje = 1.14 kg        → Masa del fuselaje
mTelemetría= 0.10 kg       → Masa del sistema de telemetría
mParacaidas= 0.05 kg       → Masa del paracaídas
mPayload  = 0.52 kg        → Masa de la carga útil (payload)
CD        = 0.40           → Coeficiente de arrastre aerodinámico del cohete
[Diam_cohete = 3 pulgadas = 0.0762 m] → hardcodeado como =0.0254*3
```

### 4.2 Inputs referenciados de Diseño (automáticos)

```
mp        ← Diseño.mp      → Masa de propelente [kg]
a, n, ρP  ← Diseño         → Parámetros de combustión
re, Lg, ri, ng ← Diseño    → Geometría del grano
At, A2    ← Diseño         → Áreas de la tobera
ηnozzle   ← Diseño         → Eficiencia de tobera
M2        ← Diseño         → Mach de salida
TQ        ← Diseño         → Tiempo de quemado
c*        ← Diseño         → Velocidad característica
T1, k, R  ← Diseño         → Propiedades termodinámicas
```

### 4.3 Inputs constantes físicas

```
PSTD   = 101325 Pa          → Presión estándar ISA
ge     = 9.780318 m/s²      → Gravedad en el ecuador
f      = 0.0053024           → Coeficiente de achatamiento gravitacional
f4     = 5.8×10⁻⁶           → Coeficiente gravitacional de 4to orden
A      = 3.086×10⁻⁶ s⁻²     → Gradiente vertical de gravedad
L      = 0.0065 K/m          → Gradiente adiabático ambiental
T0     = 288.15 K            → Temperatura estándar al nivel del mar
M_aire = 0.0289644 kg/mol   → Masa molar del aire seco
R_univ = 8.31447 J/mol·K    → Constante universal de gas ideal
```

### 4.4 Masas derivadas (calculadas una vez, no por paso)

```
mMuerta   = mMotor + mFuselaje + mTelemetría + mParacaidas + mPayload
mInicial  = mMuerta + mp
m0        = mInicial - mPayload   → Masa inicial propulsiva
AT        = π·(Diam/2)²           → Área transversal del cohete [m²]
mVT       = (PSTD · Vtotal) / (R · T1) → Masa del gas inicial en la cámara
```

### 4.5 Variables calculadas por paso de tiempo i (simulación)

**Subfase A — durante quemado (t ≤ TQ):**

```
COLUMNA        FÓRMULA / LÓGICA
Patm(t)        = PSTD · (1 - L·z(t)/T0)^(M_aire·g_local/(R_univ·L))  [Pa]
Tatm(t)        = T0 - L·z(t)                                           [K]
ρatm(t)        = Patm·M_aire / (R_univ·Tatm)                          [kg/m³]
g_local(t)     = ge·(1+A·sin²ϕ-f4·sin²2ϕ)·(1 - 2·(z+HInic)/Re)     [m/s²]

[toda la balística interna idéntica al Módulo 3:]
br, Rinst, Linst, Atrans, Along, Ab, Ab-T, VT, MT, MG,
m'prod, M'escp, Δm, Mi, VL, Kn, Pe, P2, CF, CF_adj

F(t)           = CF_adj · At · Pc                   [N]  → empuje
IT(t)          = Σ F·Δt                             [N·s] → impulso acumulado

mC(t)          = mMuerta + mp(t)                   [kg]  → masa del cohete en t
WC(t)          = mC · g_local                      [N]   → peso
FD(t)          = 0.5·ρatm·v²·CD·AT                [N]   → arrastre
FNet(t)        = F - WC - FD                       [N]   → fuerza neta
a_coh(t)       = FNet / mC                         [m/s²]→ aceleración del cohete
v(t)           = v(t-1) + a·Δt                    [m/s] → integración Euler
z(t)           = z(t-1) + v(t-1)·Δt              [m]   → posición sobre el suelo
h(t)           = z(t) + HInic                      [m]   → altitud absoluta
```

**Subfase B — vuelo libre (t > TQ, v > 0, motor apagado):**

```
F(t)   = 0
mC(t)  = mMuerta (masa muerta únicamente, propelente agotado)
FNet   = -WC - FD
[resto de variables igual]
```

**Subfase C — descenso (v < 0):**

```
El simulador continúa hasta apogeo (v = 0)
FD     = 0.5·ρatm·v²·CD·AT (sigue actuando en descenso, dirección opuesta)
```

### 4.6 Outputs finales (resumen de la simulación)

```
OUTPUT              CÓMO SE OBTIENE
zMAX      [m]     = MAX(z(t)) → altura máxima sobre el punto de lanzamiento
hMAX      [m]     = zMAX + HInic → altitud máxima absoluta (sobre nivel del mar)
vMAX      [m/s]   = MAX(v(t)) → velocidad máxima alcanzada
vMAX_kmh  [km/h]  = vMAX · 3.6
MMAX      [-]     = vMAX / 343.2 → Mach máximo (velocidad del sonido estándar)
aMAX      [m/s²]  = MAX(a(t)) → aceleración máxima
aMAX_g    [g's]   = aMAX / 9.81
FMAX      [N]     = MAX(F(t)) → empuje máximo durante el quemado
tApogee   [s]     = VLOOKUP(zMAX, tabla z vs t) → tiempo al apogeo
tBurnout  [s]     = VLOOKUP(vMAX, tabla v vs t) → tiempo al fin de quemado
zBurnout  [m]     = altura al fin de quemado
MR        [-]     = (mMuerta - mPayload) / m0 → razón de masas
ζ         [-]     = mp / m0 → fracción másica de propelente
```

---

## Árbol de dependencias entre módulos

```
[USUARIO INGRESA]
        │
        ▼
┌─────────────────┐
│  Hoja: Diseño   │
│  (Módulo 1)     │
│                 │
│ P1, T1, ng, ri, │
│ re, Lg, Sg, a,  │
│ n, ρP, k, R,    │
│ DEXT, Esp,      │
│ materiales,     │
│ tornillos,      │
│ ángulos tobera  │
└────────┬────────┘
         │ re, ri, Lg, TQ, br
         ▼
┌─────────────────────┐
│ Hoja: Coport. Area  │
│ (Módulo 2)          │
│                     │
│ → Ab(t) paso a paso │
│ → Ab_promedio       │◄──── regresa Ab_prom, σ_Ab a Diseño
│ → σ(Ab)             │
└──────────┬──────────┘
           │ Ab_prom, REGRESA a Diseño
           │
           │ (Diseño usa Ab para calcular ṁ, F, At, etc.)
           │
           ▼
┌───────────────────────────────┐
│ Hoja: Comportamiento en       │
│ el Tiempo (Módulo 3)          │
│                               │
│ → Pc(t), br(t), F(t), IT(t)  │
│ → Kn(t), ṁ(t)               │◄─── regresa Pmax, IT_esp,
│ → tabla completa 1000 pasos  │     Isp_esp, F_prom, F_max
└──────────────┬────────────────┘
               │ Pmax → análisis estructural en Diseño
               │ IT_esp, Isp_esp, F → resumen en Diseño
               │
               ▼
┌──────────────────────────────────────┐
│  Hoja: Simulador de Altitud          │
│  (Módulo 4)                          │
│  [inputs adicionales del cohete]     │
│                                      │
│  → v(t), z(t), a(t), F(t)           │
│  → tabla completa ~3000+ pasos       │
│                                      │
│  OUTPUTS FINALES:                    │
│  zMAX, hMAX, vMAX, MMAX, aMAX,      │
│  FMAX, tApogee, tBurnout, zBurnout,  │
│  MR, ζ                               │
└──────────────────────────────────────┘
```

---

## Nota sobre el paso de tiempo en cada módulo

| Módulo | Δt | Pasos totales |
|---|---|---|
| Coport. de Area | TQ / 1000 | ~1000 |
| Comportamiento en el Tiempo | TQ / 1000 ≈ 8.14×10⁻⁴ s | ~1000 (solo fase quemado) |
| Simulador de Altitud (quemado) | TQ / 1000 | ~1000 |
| Simulador de Altitud (vuelo libre) | variable, mismo Δt | ~2000–2500 adicionales |

> **Para el repositorio:** cada módulo puede implementarse como una función pura que recibe sus inputs y devuelve un arreglo de resultados por paso de tiempo, más un diccionario de outputs de resumen. Los módulos 3 y 4 comparten la misma lógica de balística interna durante la fase de quemado.
