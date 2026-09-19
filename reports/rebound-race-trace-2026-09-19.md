# Rebound race — trace

Eight real misses (sim arm, `_is_full_simulation` True at Pattern A, `SEED_DEFENSES=1`,
seeds 8000-8002), each showing who wins under **arrival-only** and under **arrival + race**.

Both winners are computed on the SAME miss: the counterfactual runs with the sim RNG state
saved and restored, so **the `randint(1,6)` dice are identical in both columns** and any change
of winner comes from the term alone.

Grid: x 58-96 left to right at 2 units per character, y 2-48 bottom to top, attacking the rim on
the right (`R`); away-attacking misses are mirrored into this frame. `o` = the bounce.
Lower-case = where the player stood at the shot; UPPER-CASE = where he ARRIVES.

`dist` is arrival distance to the bounce. `rate` is his standard travel rate
(`_ag_grid_per_game_sec`). `time` = dist / rate — the quantity the race term scores.

Read with `reports/rebound-race-2026-09-19.md`.

---

### 1. seed 8000 — WINNER CHANGES   (AG spread in the field: 81)

window 1.27s

```
|                    
|                    
|               g    
|                    
|                    
|                    
|                b   
|                    
|              dh    
|                    
|              GiI   
|      j        JC   
|              H R   
|      E             
|                    
|                    
|        o       c   
|               f    
|                    
|                    
|                    
|                    
|                    
|                    
```

| | player | side | AG | rate | dist | **time** |
|---|---|---|---|---|---|---|
| `a`  | Xenon Fletcher | DEF | 68 | 14.50 | 13.8 | 0.949 |
| `b`  | Benny Pena | OFF | 57 | 14.20 | 19.9 | 1.405 |
| `c` **RACE** | Omar Nola | DEF | 48 | 13.94 | 18.0 | 1.288 |
| `d`  | CJ Castleman | DEF | 22 | 13.22 | 14.6 | 1.104 |
| `e` ARRIVAL | Wilbert Struthers | OFF | 75 | 14.70 | 8.9 | 0.604 |
| `f`  | Joey Giblin | OFF | 34 | 13.55 | 14.0 | 1.036 |
| `g`  | Ellis Clemons | OFF | 26 | 13.33 | 17.8 | 1.338 |
| `h`  | Clint Workman | DEF | 73 | 14.64 | 15.2 | 1.035 |
| `i`  | Damon Martin | OFF | 10 | 12.88 | 19.9 | 1.548 |
| `j`  | Ronnie Rozier | DEF | 91 | 15.15 | 17.4 | 1.148 |

### 2. seed 8002 — WINNER CHANGES   (AG spread in the field: 78)

window 1.47s

```
|                    
|                    
|                    
|                    
|                    
|      o             
|                    
|                    
|         ha  ic     
|              I     
|      d       GB    
|                    
|       b     eEAR   
|                    
|              D C   
|                    
|                    
|     f              
|                    
|                    
|                    
|                    
|                    
|                    
```

| | player | side | AG | rate | dist | **time** |
|---|---|---|---|---|---|---|
| `a`  | Kent McManus | DEF | 11 | 12.91 | 22.0 | 1.706 |
| `b`  | Delmont Braggs | DEF | 41 | 13.75 | 19.2 | 1.399 |
| `c`  | Cedric Buckles | OFF | 25 | 13.30 | 26.2 | 1.968 |
| `d`  | Von Sanborn | DEF | 71 | 14.59 | 24.8 | 1.703 |
| `e` **RACE** | CJ Castleman | DEF | 23 | 13.24 | 20.5 | 1.549 |
| `f` ARRIVAL | Wilbert Struthers | OFF | 89 | 15.09 | 17.2 | 1.140 |
| `g`  | Joey Giblin | OFF | 39 | 13.69 | 19.4 | 1.418 |
| `h`  | Ellis Clemons | OFF | 34 | 13.55 | 7.8 | 0.576 |
| `i`  | Freddie Anderson | DEF | 22 | 13.22 | 17.9 | 1.354 |

### 3. seed 8001 — WINNER CHANGES   (AG spread in the field: 76)

window 1.72s

```
|        g           
|                    
|        b           
|                    
|        i  a        
|                    
|                    
|          c         
|f                   
|                    
|           E        
|          J GB      
|        d     e R   
|           F        
|            D       
|          o   AH    
|                    
|                    
|                    
|                    
| j                  
|                    
|                    
|                    
```

| | player | side | AG | rate | dist | **time** |
|---|---|---|---|---|---|---|
| `a`  | Kent McManus | OFF | 10 | 12.88 | 8.0 | 0.621 |
| `b`  | Benny Pena | DEF | 62 | 14.34 | 10.0 | 0.698 |
| `c`  | Omar Nola | OFF | 49 | 13.97 | 9.4 | 0.675 |
| `d` ARRIVAL | Cedric Buckles | DEF | 26 | 13.33 | 3.6 | 0.271 |
| `e` **RACE** | Wilbert Struthers | DEF | 86 | 15.01 | 9.2 | 0.614 |
| `f`  | Pete Del Fino | OFF | 10 | 12.88 | 3.9 | 0.301 |
| `g`  | Ellis Clemons | DEF | 30 | 13.44 | 10.0 | 0.745 |
| `h`  | Roger Henrich | DEF | 24 | 13.27 | 10.0 | 0.753 |
| `i`  | Freddie Anderson | OFF | 24 | 13.27 | 22.6 | 1.700 |
| `j`  | Ronnie Rozier | OFF | 82 | 14.90 | 8.0 | 0.537 |

### 4. seed 8001 — WINNER CHANGES   (AG spread in the field: 76)

window 1.15s

```
|                    
|                    
|                    
|                    
|                    
|                    
|                    
|                    
|                    
|                    
|                o   
|                    
|                R   
|                    
|              e     
|                    
|                    
|                    
|                    
|                    
|                    
|                    
|                    
|                    
```

| | player | side | AG | rate | dist | **time** |
|---|---|---|---|---|---|---|
| `a`  | Kent McManus | DEF | 10 | 12.88 | 54.9 | 4.263 |
| `b`  | Benny Pena | OFF | 62 | 14.34 | 51.1 | 3.567 |
| `c`  | Omar Nola | DEF | 49 | 13.97 | 54.0 | 3.863 |
| `d`  | Cedric Buckles | OFF | 26 | 13.33 | 51.9 | 3.893 |
| `e` ARRIVAL | Wilbert Struthers | OFF | 86 | 15.01 | 8.5 | 0.569 |
| `f`  | Pete Del Fino | DEF | 10 | 12.88 | 54.6 | 4.242 |
| `g`  | Ellis Clemons | OFF | 30 | 13.44 | 53.1 | 3.952 |
| `h`  | Roger Henrich | OFF | 24 | 13.27 | 56.2 | 4.235 |
| `i` **RACE** | Freddie Anderson | DEF | 24 | 13.27 | 48.0 | 3.614 |
| `j`  | Ronnie Rozier | DEF | 82 | 14.90 | 52.0 | 3.491 |

### 5. seed 8000 — WINNER CHANGES   (AG spread in the field: 75)

window 1.27s

```
|                    
|                    
|            a       
|                    
|            b       
|                    
|     i          d   
|                    
|              g h   
|               f    
|               H    
|             IAe    
|              E o   
|               BG   
|              F     
|                    
|                    
|                    
|                    
|                    
|                    
|                    
|                    
|                    
```

| | player | side | AG | rate | dist | **time** |
|---|---|---|---|---|---|---|
| `a`  | Xenon Fletcher | OFF | 62 | 14.34 | 2.8 | 0.196 |
| `b`  | Benny Pena | DEF | 52 | 14.06 | 1.2 | 0.086 |
| `c` ARRIVAL | Omar Nola | OFF | 45 | 13.86 | 2.2 | 0.161 |
| `d`  | CJ Castleman | OFF | 20 | 13.16 | 12.0 | 0.912 |
| `e`  | Joey Giblin | DEF | 31 | 13.47 | 2.0 | 0.149 |
| `f`  | Ellis Clemons | DEF | 21 | 13.19 | 4.2 | 0.322 |
| `g`  | Clint Workman | OFF | 68 | 14.50 | 2.0 | 0.138 |
| `h`  | Damon Martin | DEF | 8 | 12.82 | 5.1 | 0.398 |
| `i` **RACE** | Ronnie Rozier | OFF | 83 | 14.92 | 5.2 | 0.350 |

### 6. seed 8001 — same winner   (AG spread in the field: 77)

window 1.62s

```
|                    
|                    
|                    
|                    
|                    
|         a          
|                    
|                    
|           c I      
|          o A  i    
|           gF G     
|            h C     
|  f     b  H    R   
|              dD    
|            E  B    
|                    
|                    
|                    
|                    
|            e       
|            j       
|                    
|                    
|                    
```

| | player | side | AG | rate | dist | **time** |
|---|---|---|---|---|---|---|
| `a`  | Kent McManus | OFF | 10 | 12.88 | 3.0 | 0.233 |
| `b`  | Benny Pena | DEF | 63 | 14.36 | 14.2 | 0.989 |
| `c`  | Omar Nola | OFF | 50 | 14.00 | 8.9 | 0.639 |
| `d`  | Cedric Buckles | DEF | 27 | 13.36 | 12.0 | 0.902 |
| `e`  | Wilbert Struthers | DEF | 87 | 15.04 | 9.8 | 0.655 |
| `f`  | Pete Del Fino | OFF | 10 | 12.88 | 3.5 | 0.275 |
| `g`  | Ellis Clemons | DEF | 31 | 13.47 | 8.1 | 0.599 |
| `h` ARRIVAL **RACE** | Roger Henrich | DEF | 25 | 13.30 | 7.1 | 0.532 |
| `i`  | Freddie Anderson | OFF | 24 | 13.27 | 5.1 | 0.384 |
| `j`  | Ronnie Rozier | OFF | 87 | 15.04 | 23.1 | 1.535 |

### 7. seed 8002 — same winner   (AG spread in the field: 73)

window 1.80s

```
|                    
|                    
|                    
|                    
|        a           
|                    
|                    
|            o       
|          iA  d     
|                    
|            G       
|                    
|   fh    b  I J R   
|                    
|           cB DH    
|           g        
|          e         
|                    
|                    
|        j           
|                    
|                    
|                    
|                    
```

| | player | side | AG | rate | dist | **time** |
|---|---|---|---|---|---|---|
| `a`  | Xenon Fletcher | OFF | 78 | 14.78 | 3.6 | 0.244 |
| `b`  | Stuart Marconi | DEF | 10 | 12.88 | 15.0 | 1.167 |
| `c`  | Kermit Prospect | OFF | 23 | 13.24 | 9.1 | 0.684 |
| `d`  | CJ Castleman | OFF | 20 | 13.16 | 14.9 | 1.130 |
| `e`  | Wilbert Struthers | DEF | 72 | 14.62 | 10.3 | 0.704 |
| `f`  | Trent Athens | OFF | 59 | 14.25 | 20.1 | 1.412 |
| `g` ARRIVAL **RACE** | Roger Henrich | DEF | 18 | 13.10 | 6.1 | 0.464 |
| `h`  | Ervin Miller | DEF | 58 | 14.22 | 16.2 | 1.136 |
| `i`  | Norris Khan | DEF | 57 | 14.20 | 11.1 | 0.778 |
| `j`  | Ronnie Rozier | OFF | 83 | 14.92 | 11.2 | 0.749 |

### 8. seed 8000 — same winner   (AG spread in the field: 71)

window 1.62s

```
|                    
|                    
|               i    
|                    
|                e   
|                    
|        a           
|                    
|             bg     
|                    
|            F C     
|      f     h       
|   d          EBR   
|                    
|            D c     
|           HG o     
|                    
|                    
|                    
|                    
|                    
|                    
|                    
|                    
```

| | player | side | AG | rate | dist | **time** |
|---|---|---|---|---|---|---|
| `a`  | Xenon Fletcher | DEF | 72 | 14.62 | 6.1 | 0.416 |
| `b`  | Omar Nola | DEF | 52 | 14.06 | 5.4 | 0.383 |
| `c`  | Stuart Marconi | OFF | 13 | 12.96 | 9.1 | 0.699 |
| `d` ARRIVAL **RACE** | Wilbert Struthers | OFF | 84 | 14.95 | 3.6 | 0.241 |
| `e`  | Trent Athens | DEF | 65 | 14.42 | 6.1 | 0.422 |
| `f`  | Clint Workman | DEF | 84 | 14.95 | 12.1 | 0.808 |
| `g`  | Roger Henrich | OFF | 22 | 13.22 | 3.0 | 0.227 |
| `h`  | Freddie Anderson | DEF | 24 | 13.27 | 6.0 | 0.452 |
| `i`  | Norris Khan | OFF | 68 | 14.50 | 26.1 | 1.798 |

