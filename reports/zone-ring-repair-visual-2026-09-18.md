# Zone ring repair — before and after

Every panel is a **zoomed** half-court window: x 62-92 left to right at 1 unit per character, y 4-46 bottom to
top at 2 units per row ('upper' spots are the top of the panel), offense attacking the rim on the right (`R`).
`#` = a point the ray-cast `_point_in_polygon` reports as INSIDE that defender's zone. `*` = a listed spot
(a polygon vertex — a vertex is on the boundary, so it counts as inside even where the `#` fill around it is
thin). `.` = a neighbouring defender's zone, shown only in the design-call panels for context.

**BEFORE is today's list order. AFTER is the same spots in a repaired order — no spot added, none removed.**
Areas are the ray-cast interior measured at 0.25-unit resolution.

Nothing here is landed. Read this with `reports/zone-ring-repair-2026-09-18.md`.

---

## Part 1 — the 14 self-intersecting rings


### 2-3 normal — PG

Clean: every spot is a corner of the region, so the repaired ring is the only sane simple ring through them.

```
BEFORE  area 159.3                AFTER   area 212.6
--------------------------------- ---------------------------------
|                                |                               
|                                |                               
|                 ##*            |                 ##*           
|           *######              |           *#######            
|         #########              |         ##########            
|      *##########               |      *############            
|      ##########                |      #############            
|     ##########                 |     ##############            
|    ##########                  |    ###############            
|    ##########                  |    ###############            
|  *#########*     *         R   |  *#########*#####*         R  
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
--------------------------------- ---------------------------------
```

- before: `['key', 'midLane', 'topLane', 'upper midCorner', 'upper wing', 'upper midWing']`
- after:  `['key', 'topLane', 'midLane', 'upper midCorner', 'upper wing', 'upper midWing']`

### 2-3 normal — SF

**1 spot(s) lie inside the convex hull of the set**, so the repaired ring carries a notch or a thin spike around them — it reaches 94% of the hull area. Judge the notch.

```
BEFORE  area 55.2                 AFTER   area 92.3
--------------------------------- ---------------------------------
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                            R   |                            R  
|                                |                               
|                                |                               
|                                |                               
|                  *#####*       |                  *#####*      
|                  #######       |                  ######       
|                  *    * ##*    |                  *####*###*   
|                        ##      |                   ########    
|                      ####      |                   ########    
|                    ######      |                   ########    
|                   *      *     |                   *      *    
|                                |                               
--------------------------------- ---------------------------------
```

- before: `['lower midCorner', 'lower corner', 'lower lowPost', 'lower midPost', 'lower apex', 'lower bird', 'lower midBaseline']`
- after:  `['lower apex', 'lower midCorner', 'lower corner', 'lower midBaseline', 'lower bird', 'lower lowPost', 'lower midPost']`

### 2-3 normal — PF

**1 spot(s) lie inside the convex hull of the set**, so the repaired ring carries a notch or a thin spike around them — it reaches 94% of the hull area. Judge the notch.

```
BEFORE  area 51.7                 AFTER   area 84.3
--------------------------------- ---------------------------------
|                                |                               
|                          *     |                          *    
|                   * #####      |                   *#######    
|                       ###      |                   ########    
|                         #      |                   ########    
|                  *####*###*    |                  *####*###*   
|                  #######       |                  ######       
|                  *#####*       |                  *#####*      
|                                |                               
|                                |                               
|                            R   |                            R  
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
--------------------------------- ---------------------------------
```

- before: `['upper midCorner', 'upper corner', 'upper lowPost', 'upper midPost', 'upper apex', 'upper bird', 'upper midBaseline']`
- after:  `['upper midPost', 'upper lowPost', 'upper bird', 'upper midBaseline', 'upper corner', 'upper midCorner', 'upper apex']`

### 2-3 lower shift — SG

**2 spot(s) lie inside the convex hull of the set**, so the repaired ring carries a notch or a thin spike around them — it reaches 96% of the hull area. Judge the notch.

```
BEFORE  area 119.1                AFTER   area 151.4
--------------------------------- ---------------------------------
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                            R   |                            R  
|                                |                               
|                                |                               
|                                |                               
|            * ####*             |            *#####*#           
|                #               |            ##########         
|               ###*####*###*    |            ######*####*###*   
|             ##############     |            ###############    
|           *###############     |           *###############    
|                 ##########     |                 ##########    
|                   *      *     |                   *      *    
|                                |                               
--------------------------------- ---------------------------------
```

- before: `['lower corner', 'lower midCorner', 'lower wing', 'lower midPost', 'lower highPost', 'lower apex', 'lower bird', 'lower midBaseline']`
- after:  `['lower wing', 'lower midCorner', 'lower corner', 'lower midBaseline', 'lower apex', 'lower bird', 'lower midPost', 'lower highPost']`

### 2-3 lower shift — SF

**1 spot(s) lie inside the convex hull of the set**, so the repaired ring carries a notch or a thin spike around them — it reaches 94% of the hull area. Judge the notch.

```
BEFORE  area 55.2                 AFTER   area 92.3
--------------------------------- ---------------------------------
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                            R   |                            R  
|                                |                               
|                                |                               
|                                |                               
|                  *#####*       |                  *#####*      
|                  #######       |                  ######       
|                  *    * ##*    |                  *####*###*   
|                        ##      |                   ########    
|                      ####      |                   ########    
|                    ######      |                   ########    
|                   *      *     |                   *      *    
|                                |                               
--------------------------------- ---------------------------------
```

- before: `['lower midCorner', 'lower corner', 'lower lowPost', 'lower midPost', 'lower apex', 'lower bird', 'lower midBaseline']`
- after:  `['lower apex', 'lower midCorner', 'lower corner', 'lower midBaseline', 'lower bird', 'lower lowPost', 'lower midPost']`

### 2-3 lower shift — PF

**1 spot(s) lie inside the convex hull of the set**, so the repaired ring carries a notch or a thin spike around them — it reaches 94% of the hull area. Judge the notch.

```
BEFORE  area 51.7                 AFTER   area 84.3
--------------------------------- ---------------------------------
|                                |                               
|                          *     |                          *    
|                   * #####      |                   *#######    
|                       ###      |                   ########    
|                         #      |                   ########    
|                  *####*###*    |                  *####*###*   
|                  #######       |                  ######       
|                  *#####*       |                  *#####*      
|                                |                               
|                                |                               
|                            R   |                            R  
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
--------------------------------- ---------------------------------
```

- before: `['upper midCorner', 'upper corner', 'upper lowPost', 'upper midPost', 'upper apex', 'upper bird', 'upper midBaseline']`
- after:  `['upper midPost', 'upper lowPost', 'upper bird', 'upper midBaseline', 'upper corner', 'upper midCorner', 'upper apex']`

### 2-3 upper shift — PG

**2 spot(s) lie inside the convex hull of the set**, so the repaired ring carries a notch or a thin spike around them — it reaches 96% of the hull area. Judge the notch.

```
BEFORE  area 106.4                AFTER   area 136.4
--------------------------------- ---------------------------------
|                                |                               
|                          *     |                          *    
|                 ##*#######     |                 ##*#######    
|           *###############     |           *###############    
|             ##############     |            ###############    
|               ###*####*###*    |            ######*####*###*   
|               ##               |            #########          
|            *#####*             |            *#####*            
|                                |                               
|                                |                               
|                            R   |                            R  
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
--------------------------------- ---------------------------------
```

- before: `['upper corner', 'upper midCorner', 'upper wing', 'upper midPost', 'upper highPost', 'upper apex', 'upper bird', 'upper midBaseline']`
- after:  `['upper wing', 'upper highPost', 'upper midPost', 'upper bird', 'upper apex', 'upper midBaseline', 'upper corner', 'upper midCorner']`

### 2-3 upper shift — SF

**1 spot(s) lie inside the convex hull of the set**, so the repaired ring carries a notch or a thin spike around them — it reaches 94% of the hull area. Judge the notch.

```
BEFORE  area 55.2                 AFTER   area 92.3
--------------------------------- ---------------------------------
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                            R   |                            R  
|                                |                               
|                                |                               
|                                |                               
|                  *#####*       |                  *#####*      
|                  #######       |                  ######       
|                  *    * ##*    |                  *####*###*   
|                        ##      |                   ########    
|                      ####      |                   ########    
|                    ######      |                   ########    
|                   *      *     |                   *      *    
|                                |                               
--------------------------------- ---------------------------------
```

- before: `['lower midCorner', 'lower corner', 'lower lowPost', 'lower midPost', 'lower apex', 'lower bird', 'lower midBaseline']`
- after:  `['lower apex', 'lower midCorner', 'lower corner', 'lower midBaseline', 'lower bird', 'lower lowPost', 'lower midPost']`

### 2-3 upper shift — PF

**1 spot(s) lie inside the convex hull of the set**, so the repaired ring carries a notch or a thin spike around them — it reaches 94% of the hull area. Judge the notch.

```
BEFORE  area 51.7                 AFTER   area 84.3
--------------------------------- ---------------------------------
|                                |                               
|                          *     |                          *    
|                   * #####      |                   *#######    
|                       ###      |                   ########    
|                         #      |                   ########    
|                  *####*###*    |                  *####*###*   
|                  #######       |                  ######       
|                  *#####*       |                  *#####*      
|                                |                               
|                                |                               
|                            R   |                            R  
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
--------------------------------- ---------------------------------
```

- before: `['upper midCorner', 'upper corner', 'upper lowPost', 'upper midPost', 'upper apex', 'upper bird', 'upper midBaseline']`
- after:  `['upper midPost', 'upper lowPost', 'upper bird', 'upper midBaseline', 'upper corner', 'upper midCorner', 'upper apex']`

### 3-2 lower-corner shift — PF

**3 spot(s) lie inside the convex hull of the set**, so the repaired ring carries a notch or a thin spike around them — it reaches 89% of the hull area. Judge the notch.

```
BEFORE  area 176.4                AFTER   area 211.1
--------------------------------- ---------------------------------
|                                |                               
|                          *     |                          *    
|                   *#######     |                   *######     
|                     ######     |                   #######     
|                      #####     |                   #######     
|                       *###*    |                   ####*#  *   
|                     #####      |                   ######      
|                  *#####*       |                  *#####*      
|                  #######       |                  ####### #    
|                  #######       |                  ####### #    
|                  *######*  R   |                  *######*# R  
|                   #######      |                   ########    
|                    ######      |                    #######    
|                     #####      |                     ######    
|                     #####      |                     ######    
|                      ####      |                      #####    
|                       ###      |                       ####    
|                        ##      |                        ###    
|                         #      |                         ##    
|                                |                          #    
|                          *     |                          *    
|                                |                               
--------------------------------- ---------------------------------
```

- before: `['basketSpot', 'midLane', 'upper midPost', 'upper bird', 'upper midCorner', 'upper corner', 'upper midBaseline', 'upper lowPost', 'basketSpot', 'midLane', 'lower corner']`
- after:  `['midLane', 'lower corner', 'upper midBaseline', 'basketSpot', 'upper bird', 'upper lowPost', 'upper corner', 'upper midCorner', 'upper midPost']`

### 3-2 upper-corner shift — C

**3 spot(s) lie inside the convex hull of the set**, so the repaired ring carries a notch or a thin spike around them — it reaches 89% of the hull area. Judge the notch.

```
BEFORE  area 175.7                AFTER   area 211.1
--------------------------------- ---------------------------------
|                                |                               
|                          *     |                          *    
|                                |                          #    
|                         #      |                         ##    
|                        ##      |                        ###    
|                       ###      |                       ####    
|                      ####      |                      #####    
|                     #####      |                     ######    
|                     #####      |                     ######    
|                    ######      |                    #######    
|                  *######*  R   |                  *######*# R  
|                  #######       |                  ####### #    
|                  #######       |                  ####### #    
|                  #######       |                  ####### #    
|                  * ####*       |                  *#####*      
|                      #####     |                   ######      
|                       *###*    |                   ####*#  *   
|                      #####     |                   #######     
|                     ######     |                   #######     
|                    #######     |                   #######     
|                   *      *     |                   *      *    
|                                |                               
--------------------------------- ---------------------------------
```

- before: `['basketSpot', 'midLane', 'lower midPost', 'lower bird', 'lower midCorner', 'lower corner', 'lower midBaseline', 'lower lowPost', 'basketSpot', 'midLane', 'upper corner']`
- after:  `['lower midPost', 'lower midCorner', 'lower corner', 'lower lowPost', 'lower bird', 'basketSpot', 'lower midBaseline', 'upper corner', 'midLane']`

### 1-3-1 normal — C

**4 spot(s) lie inside the convex hull of the set**, so the repaired ring carries a notch or a thin spike around them — it reaches 91% of the hull area. Judge the notch.

```
BEFORE  area 123.7                AFTER   area 224.6
--------------------------------- ---------------------------------
|                                |                               
|                          *     |                          *    
|                          #     |                               
|                          #     |                         #     
|                          #     |                        ##     
|                          #*    |                       ### *   
|                                |                      #### #   
|                        *#      |                     ###*# #   
|                         #      |                     ### ###   
|                         #      |                    #### ###   
|                  *      *  R   |                  *##### *##R  
|                  #######       |                  ###### ###   
|                  #######       |                  ###### ###   
|                  #######       |                  ###### ###   
|                  * ####*       |                  *#####*###   
|                      #####     |                   #########   
|                       *###*    |                   ####*###*   
|                      #####     |                   ########    
|                     ######     |                   ########    
|                    #######     |                   ########    
|                   *      *     |                   *      *    
|                                |                               
--------------------------------- ---------------------------------
```

- before: `['basketSpot', 'upper corner', 'upper midBaseline', 'upper lowPost', 'basketSpot', 'lower lowPost', 'lower midBaseline', 'lower corner', 'lower midCorner', 'lower bird', 'lower midPost', 'midLane', 'basketSpot']`
- after:  `['lower midPost', 'lower midCorner', 'lower corner', 'lower midBaseline', 'upper midBaseline', 'lower lowPost', 'lower bird', 'upper lowPost', 'basketSpot', 'upper corner', 'midLane']`

### 1-3-1 lower shift — C

Clean: every spot is a corner of the region, so the repaired ring is the only sane simple ring through them.

```
BEFORE  area 14.2                 AFTER   area 27.2
--------------------------------- ---------------------------------
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                         *  R   |                         *  R  
|                         #      |                         #     
|                         #      |                         #     
|                         #      |                         ##    
|                        *#      |                        *##    
|                          #     |                         ##    
|                          #*    |                         ##*   
|                          #     |                          #    
|                          #     |                          #    
|                          #     |                          #    
|                          *     |                          *    
|                                |                               
--------------------------------- ---------------------------------
```

- before: `['basketSpot', 'lower lowPost', 'lower midBaseline', 'lower corner']`
- after:  `['lower lowPost', 'lower corner', 'lower midBaseline', 'basketSpot']`

### 1-3-1 upper shift — C

Clean: every spot is a corner of the region, so the repaired ring is the only sane simple ring through them.

```
BEFORE  area 13.9                 AFTER   area 27.2
--------------------------------- ---------------------------------
|                                |                               
|                          *     |                          *    
|                          #     |                          #    
|                          #     |                          #    
|                          #     |                         ##    
|                          #*    |                         ##*   
|                                |                         ##    
|                        *#      |                        *##    
|                         #      |                         #     
|                         #      |                         #     
|                         *  R   |                         *  R  
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
|                                |                               
--------------------------------- ---------------------------------
```

- before: `['basketSpot', 'upper lowPost', 'upper midBaseline', 'upper corner']`
- after:  `['upper lowPost', 'basketSpot', 'upper midBaseline', 'upper corner']`

---

## Part 2 — the two single-spot zones (DESIGN CALL — nothing chosen)

`ZONE_131_LOWER_CORNER_SHIFT["C"] = ["lower corner"]` and its mirror
`ZONE_131_UPPER_CORNER_SHIFT["C"] = ["upper corner"]` are one point each. `_point_in_polygon` returns
False for any list shorter than 3, so **today these two defenders match nobody, ever** — the left panel
below is empty, which is literally what the code sees.

`.` marks the other four defenders' zones in the same shift, so the hole is visible. The lower-corner version
is shown; the upper-corner one is its mirror and would take the mirrored spots.


### Candidate A — corner pocket

C closes out the corner and the short baseline behind it. SF keeps the wing but now shares `lower midCorner` with C, so the corner is double-covered and the overlap rung decides. The rim stays PF's. Fills 3 of the 4 holes; `basketSpot` stays uncovered.

```
TODAY   area 0.0 (empty)          CAND A  area 49.3
--------------------------------- ---------------------------------
|                                |                               
|                          .     |                          .    
|                 ..........     |                 ..........    
|           ................     |           ................    
|         ..................     |         ..................    
|      ......................    |      ......................   
|      ....................      |      ....................     
|     ....................       |     ....................      
|    ......  ...........         |    ......  ...........        
|    ...     .........           |    ...     .........          
|   .        .......         R   |   .        .......         R  
|   .................            |   .................           
|    ..................          |    ..................         
|    ....................        |    ....................       
|     .........                  |     .........                 
|      ...........               |      ...........              
|      ...........               |      ...........      *###*   
|         .....                  |         .....        #####    
|           ...                  |           ...       ######    
|                 .              |                 .  #######    
|                          *     |                   *      *    
|                                |                               
--------------------------------- ---------------------------------
```

- spots: `['lower corner', 'lower midCorner', 'lower bird', 'lower midBaseline']`
- ring order: `['lower midCorner', 'lower corner', 'lower midBaseline', 'lower bird']`

### Candidate B — corner + baseline to the rim

C becomes the baseline defender: corner, baseline drive lane and the rim. Fills all four holes including `basketSpot`. PF now shares `lower lowPost` with C. This is the biggest change to who guards what.

```
TODAY   area 0.0 (empty)          CAND B  area 38.1
--------------------------------- ---------------------------------
|                                |                               
|                          .     |                          .    
|                 ..........     |                 ..........    
|           ................     |           ................    
|         ..................     |         ..................    
|      ......................    |      ......................   
|      ....................      |      ....................     
|     ....................       |     ....................      
|    ......  ...........         |    ......  ...........        
|    ...     .........           |    ...     .........          
|   .        .......         R   |   .        .......      *  R  
|   .................            |   .................     #     
|    ..................          |    ..................   #     
|    ....................        |    .................... ##    
|     .........                  |     .........          *##    
|      ...........               |      ...........       ###    
|      ...........               |      ...........      *###*   
|         .....                  |         .....          ###    
|           ...                  |           ...           ##    
|                 .              |                 .        #    
|                          *     |                          *    
|                                |                               
--------------------------------- ---------------------------------
```

- spots: `['lower corner', 'lower midBaseline', 'basketSpot', 'lower lowPost', 'lower bird']`
- ring order: `['lower bird', 'lower corner', 'lower midBaseline', 'basketSpot', 'lower lowPost']`

### Candidate C — corner + short baseline

The middle option: corner plus the baseline up to the low post, rim still PF's. Smallest area of the three, least disruption to the other four zones.

```
TODAY   area 0.0 (empty)          CAND C  area 26.8
--------------------------------- ---------------------------------
|                                |                               
|                          .     |                          .    
|                 ..........     |                 ..........    
|           ................     |           ................    
|         ..................     |         ..................    
|      ......................    |      ......................   
|      ....................      |      ....................     
|     ....................       |     ....................      
|    ......  ...........         |    ......  ...........        
|    ...     .........           |    ...     .........          
|   .        .......         R   |   .        .......         R  
|   .................            |   .................           
|    ..................          |    ..................         
|    ....................        |    ....................       
|     .........                  |     .........          *      
|      ...........               |      ...........       ###    
|      ...........               |      ...........      *###*   
|         .....                  |         .....          ###    
|           ...                  |           ...           ##    
|                 .              |                 .        #    
|                          *     |                          *    
|                                |                               
--------------------------------- ---------------------------------
```

- spots: `['lower corner', 'lower midBaseline', 'lower lowPost', 'lower bird']`
- ring order: `['lower bird', 'lower corner', 'lower midBaseline', 'lower lowPost']`

