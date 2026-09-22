# Rebound from arrival — trace

Fifteen real misses (sim arm, `SEED_DEFENSES=1`, seeds 8000-8003), each showing every
candidate's shot-moment position, crash destination and **arrival** point, the bounce,
and who wins under each rule.

Grid: x 58-96 left to right at 2 units per character, y 2-48 bottom to top, attacking the
rim on the right (`R`). Away-attacking shots are mirrored into this frame so every panel reads
the same way. `o` = the bounce. Each candidate gets a letter: **lower-case** is
where he stood when the shot went up, **UPPER-CASE** is where he ARRIVES. Where he only
shows upper-case he has reached his destination; the gap between the two letters is how
far he actually travelled.

`BEFORE` is the legacy rule (score from shot-moment position); `AFTER` is arrival. Both
winners are computed on the SAME miss - the counterfactual runs with the sim RNG state
saved and restored, so the game is unchanged. The `randint(1,6)` dice are identical in
both columns, so any change of winner comes from position alone.

Scores: `composite` is RB*0.5 + ST*0.3 + IQ*0.1 + CH*0.1 (the dice and the team bonus are
applied on top, and are the same for both rules). `dist` columns are distance to the
bounce. `got` is the share of the way to his destination he covered.

Read with `reports/rebound-arrival-2026-09-19.md`.

---

### 1. bounce 2.0 units from the rim — WINNER CHANGES

window 0.98s

```
|                    
|                    
|               a    
|                    
|                    
|                    
|                    
|            e       
|                    
|               A    
|          g   F G   
|              H     
|              B o   
|                    
|           I  cDb   
|              D     
|                    
|     i              
|             h      
|                    
|            d       
|                    
|                    
|                    
```

| | player | side | AG | composite | dist@shot | dist@arrival | got |
|---|---|---|---|---|---|---|---|
| `a`  | Xenon Fletcher | OFF | 70 | 28.9 | 19.0 | 5.1 | 84% |
| `b` BEFORE | Cedric Buckles | DEF | 22 | 66.0 | 6.0 | 3.6 | 100% |
| `c`  | Kermit Prospect | OFF | 19 | 53.0 | 6.7 | - | - |
| `d`  | CJ Castleman | OFF | 22 | 70.4 | 19.7 | 6.8 | 83% |
| `e`  | Joey Giblin | DEF | 33 | 19.7 | 11.8 | 3.2 | 100% |
| `f` **AFTER** | Roger Henrich | DEF | 21 | 69.5 | 6.0 | 2.8 | 100% |
| `g`  | Timmy Depaz | DEF | 40 | 15.9 | 12.7 | 3.0 | 100% |
| `h`  | Norris Khan | DEF | 55 | 42.7 | 13.0 | 2.6 | 97% |
| `i`  | Ronnie Rozier | OFF | 68 | 47.7 | 23.7 | 9.5 | 71% |

### 2. bounce 2.0 units from the rim — WINNER CHANGES

window 1.52s

```
|                    
|                    
|                    
|                    
|                    
|                    
|              d     
|                    
|        c     f     
|                    
|              F     
|                    
|              HEo   
|            a       
|          e   D     
|                    
|                    
|    h               
|             b      
|          g         
|                    
|                    
|                    
|                    
```

| | player | side | AG | composite | dist@shot | dist@arrival | got |
|---|---|---|---|---|---|---|---|
| `a`  | Benny Pena | DEF | 50 | 29.9 | 8.5 | 4.1 | 100% |
| `b` BEFORE | Cedric Buckles | DEF | 18 | 55.2 | 13.9 | 4.5 | 100% |
| `c`  | Von Sanborn | OFF | 69 | 30.0 | 16.2 | - | - |
| `d`  | CJ Castleman | OFF | 19 | 60.2 | 12.7 | 6.7 | 100% |
| `e`  | Roger Henrich | DEF | 19 | 68.0 | 10.8 | 1.4 | 100% |
| `f`  | Ervin Miller | DEF | 57 | 27.3 | 7.6 | 4.2 | 100% |
| `g` **AFTER** | Freddie Anderson | OFF | 24 | 58.5 | 18.6 | 3.6 | 100% |
| `h`  | Norris Khan | DEF | 51 | 42.0 | 24.6 | 3.6 | 100% |
| `i`  | Ronnie Rozier | OFF | 57 | 35.3 | 86.2 | 64.6 | 26% |

### 3. bounce 10.3 units from the rim — WINNER CHANGES

window 1.86s

```
|                    
|                    
|               g    
|                    
|                    
|                    
|                    
|                    
|            J       
|         e  o F     
|           A EC     
|              B     
|   da  i   H  c R   
|              I     
|         f     G    
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

| | player | side | AG | composite | dist@shot | dist@arrival | got |
|---|---|---|---|---|---|---|---|
| `a`  | Xenon Fletcher | DEF | 65 | 27.5 | 16.6 | 2.8 | 100% |
| `b`  | Omar Nola | DEF | 44 | 41.5 | 6.2 | 5.0 | 100% |
| `c`  | Stuart Marconi | OFF | 9 | 46.9 | 7.1 | 5.4 | 100% |
| `d`  | Wilbert Struthers | OFF | 77 | 61.3 | 18.7 | - | - |
| `e`  | Trent Athens | DEF | 61 | 37.3 | 5.4 | 2.2 | 100% |
| `f` BEFORE | Clint Workman | DEF | 72 | 35.5 | 11.2 | 4.0 | 100% |
| `g`  | Roger Henrich | OFF | 15 | 57.8 | 15.2 | 10.8 | 100% |
| `h`  | Ervin Miller | OFF | 58 | 26.9 | 5.4 | 6.3 | 100% |
| `i` **AFTER** | Freddie Anderson | DEF | 22 | 55.8 | 11.2 | 8.5 | 100% |
| `j`  | Norris Khan | OFF | 60 | 47.4 | 5.4 | 2.2 | 100% |

### 4. bounce 10.3 units from the rim — WINNER CHANGES

window 1.62s

```
|                    
|                    
|                    
|                    
|                    
|                    
|     e              
|                    
|            H  I    
|        h   o       
|             A      
|             iB     
|              E R   
|                    
|              C     
|             JF     
|           d   c    
|     a    f         
|                    
|            b       
|            g       
|                    
|                    
|                    
```

| | player | side | AG | composite | dist@shot | dist@arrival | got |
|---|---|---|---|---|---|---|---|
| `a`  | Delmont Braggs | OFF | 36 | 12.1 | 21.3 | 3.3 | 84% |
| `b`  | Jeremy Johnson | DEF | 10 | 24.8 | 20.0 | 5.0 | 100% |
| `c` BEFORE | Cedric Buckles | DEF | 22 | 61.1 | 15.2 | 12.1 | 100% |
| `d`  | Kermit Prospect | OFF | 23 | 66.3 | 15.1 | 12.2 | 100% |
| `e`  | Pete Del Fino | OFF | 9 | 15.4 | 15.2 | 5.8 | 100% |
| `f`  | Joey Giblin | DEF | 29 | 18.0 | 16.8 | 12.7 | 100% |
| `g`  | Freddie Anderson | OFF | 23 | 57.9 | 23.0 | - | - |
| `h`  | Timmy Depaz | DEF | 36 | 22.6 | 7.0 | 1.0 | 100% |
| `i` **AFTER** | Norris Khan | DEF | 68 | 51.9 | 4.5 | 6.1 | 100% |
| `j`  | Ronnie Rozier | OFF | 73 | 44.6 | 5.6 | 12.2 | 100% |

### 5. bounce 10.3 units from the rim — WINNER CHANGES

window 1.72s

```
|                    
|                    
|            g       
|                    
|                    
|                    
|                    
|              o     
|            C       
|            H F     
|                    
|               i    
|            I E R e 
|                    
|              c   d 
|                    
|      f             
|     ab             
|                    
|                    
|            h       
|                    
|                    
|                    
```

| | player | side | AG | composite | dist@shot | dist@arrival | got |
|---|---|---|---|---|---|---|---|
| `a`  | Kent McManus | OFF | 8 | 9.1 | 26.9 | - | - |
| `b`  | Benny Pena | DEF | 53 | 34.5 | 25.0 | 3.6 | 100% |
| `c`  | Omar Nola | OFF | 45 | 42.3 | 15.0 | 4.5 | 100% |
| `d`  | Jeremy Johnson | DEF | 8 | 22.4 | 17.5 | 9.8 | 100% |
| `e` BEFORE | Stuart Marconi | DEF | 11 | 52.0 | 14.2 | 11.1 | 100% |
| `f`  | Joey Giblin | DEF | 28 | 17.2 | 23.4 | 4.0 | 100% |
| `g`  | Clint Workman | OFF | 70 | 34.7 | 10.3 | 11.4 | 100% |
| `h` **AFTER** | Freddie Anderson | OFF | 23 | 58.7 | 27.5 | 6.5 | 95% |
| `i`  | Timmy Depaz | DEF | 28 | 19.9 | 8.2 | 9.5 | 100% |

### 6. bounce 10.4 units from the rim — WINNER CHANGES

window 1.80s

```
|                    
|                    
|                    
|                    
|                    
|                    
|              jo    
|                    
|           g  E     
|        c   B       
|                    
|              D     
|hd      i  bJ  CR   
|              A e   
|            G       
|            I       
|                    
|                    
|                    
|                    
|                    
|                    
|                    
|                    
```

| | player | side | AG | composite | dist@shot | dist@arrival | got |
|---|---|---|---|---|---|---|---|
| `a`  | Kent McManus | DEF | 8 | 9.1 | 8.6 | 13.2 | 100% |
| `b`  | Cedric Buckles | OFF | 19 | 53.9 | 12.8 | 7.1 | 100% |
| `c` BEFORE | Kermit Prospect | DEF | 19 | 57.8 | 13.9 | 10.0 | 100% |
| `d`  | Von Sanborn | DEF | 65 | 20.2 | 29.7 | 9.3 | 96% |
| `e` **AFTER** | Wilbert Struthers | OFF | 69 | 56.8 | 12.3 | 4.5 | 100% |
| `f`  | Clint Workman | DEF | 67 | 33.9 | 12.5 | 15.7 | 100% |
| `g`  | Roger Henrich | OFF | 17 | 64.0 | 8.5 | 14.9 | 100% |
| `h`  | Ervin Miller | OFF | 57 | 26.4 | 32.6 | - | - |
| `i`  | Freddie Anderson | DEF | 20 | 52.6 | 16.4 | 17.7 | 100% |
| `j`  | Norris Khan | OFF | 51 | 42.3 | 3.2 | 11.2 | 100% |

### 7. bounce 38.1 units from the rim — WINNER CHANGES

window 1.27s

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
|                    
|                    
|                R   
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
|                    
```

| | player | side | AG | composite | dist@shot | dist@arrival | got |
|---|---|---|---|---|---|---|---|
| `a`  | Xenon Fletcher | OFF | 75 | 30.0 | 49.1 | 42.1 | 100% |
| `b` **AFTER** | Cedric Buckles | DEF | 25 | 73.2 | 37.6 | 43.2 | 100% |
| `c`  | Kermit Prospect | OFF | 23 | 61.8 | 34.3 | - | - |
| `d`  | CJ Castleman | OFF | 23 | 73.3 | 35.4 | 40.8 | 100% |
| `e`  | Wilbert Struthers | DEF | 83 | 67.5 | 40.5 | 40.9 | 100% |
| `f`  | Roger Henrich | DEF | 23 | 73.3 | 37.3 | 41.1 | 100% |
| `g`  | Ervin Miller | DEF | 70 | 34.7 | 48.0 | 42.8 | 100% |
| `h` BEFORE | Norris Khan | DEF | 69 | 50.9 | 30.0 | 41.2 | 100% |
| `i`  | Ronnie Rozier | OFF | 84 | 55.3 | 42.7 | 40.0 | 100% |

### 8. bounce 39.6 units from the rim — WINNER CHANGES

window 1.88s

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
|                    
|                    
|                R   
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
|                    
```

| | player | side | AG | composite | dist@shot | dist@arrival | got |
|---|---|---|---|---|---|---|---|
| `a`  | Xenon Fletcher | DEF | 61 | 30.4 | 39.4 | 39.5 | 100% |
| `b` BEFORE | Cedric Buckles | OFF | 25 | 69.7 | 33.7 | 36.0 | 100% |
| `c`  | Joey Giblin | OFF | 38 | 26.4 | 43.0 | 34.6 | 100% |
| `d`  | Clint Workman | DEF | 65 | 39.8 | 13.7 | 32.8 | 100% |
| `e` **AFTER** | Roger Henrich | OFF | 23 | 72.4 | 38.3 | 32.1 | 100% |
| `f`  | Freddie Anderson | DEF | 25 | 61.7 | 36.5 | 36.6 | 100% |
| `g`  | Norris Khan | OFF | 69 | 53.4 | 10.7 | - | - |
| `h`  | Ronnie Rozier | DEF | 76 | 47.6 | 33.6 | 34.6 | 100% |

### 9. bounce 40.5 units from the rim — WINNER CHANGES

window 1.84s

```
|                    
|                    
|                    
|                    
|                    
|         g          
|                    
|                    
|           cH  B    
|                    
|          b   Ee    
|          f         
|                R   
|                    
|           C  G     
|            F       
|                    
|                    
|                    
|        h           
|      d             
|                    
|                    
|                    
```

| | player | side | AG | composite | dist@shot | dist@arrival | got |
|---|---|---|---|---|---|---|---|
| `a`  | Omar Nola | DEF | 39 | 34.4 | 33.3 | 36.6 | 100% |
| `b`  | Delmont Braggs | DEF | 33 | 17.5 | 32.0 | 42.0 | 100% |
| `c` **AFTER** | Cedric Buckles | OFF | 22 | 62.0 | 36.2 | 29.0 | 100% |
| `d` BEFORE | Wilbert Struthers | OFF | 74 | 58.0 | 15.3 | - | - |
| `e`  | Roger Henrich | OFF | 18 | 58.2 | 40.3 | 38.8 | 100% |
| `f`  | Freddie Anderson | DEF | 22 | 56.4 | 31.3 | 30.2 | 100% |
| `g`  | Norris Khan | OFF | 51 | 42.8 | 38.4 | 34.2 | 100% |
| `h`  | Ronnie Rozier | DEF | 49 | 34.2 | 18.0 | 36.9 | 100% |

### 10. bounce 2.2 units from the rim — same winner

window 1.26s

```
|                    
|                    
|                    
|                    
|        f           
|                    
|           c        
|                    
|                    
|           b        
|            g IA    
|             FG o   
|           jh H R   
|              F     
|                D e 
|                    
|                d   
|                    
|                    
|        a           
|                    
|                    
|                    
|                    
```

| | player | side | AG | composite | dist@shot | dist@arrival | got |
|---|---|---|---|---|---|---|---|
| `a`  | Xenon Fletcher | OFF | 76 | 30.2 | 22.6 | 4.2 | 82% |
| `b`  | Cedric Buckles | DEF | 27 | 73.1 | 9.8 | 3.6 | 100% |
| `c`  | Kermit Prospect | OFF | 27 | 75.1 | 13.4 | 3.6 | 100% |
| `d`  | CJ Castleman | OFF | 24 | 76.2 | 11.0 | 5.0 | 100% |
| `e`  | Wilbert Struthers | DEF | 92 | 71.6 | 7.8 | 4.2 | 100% |
| `f`  | Trent Athens | OFF | 66 | 39.5 | 21.3 | 4.8 | 80% |
| `g` BEFORE **AFTER** | Roger Henrich | DEF | 26 | 89.4 | 6.1 | 3.0 | 100% |
| `h`  | Ervin Miller | DEF | 73 | 31.0 | 6.7 | 3.6 | 100% |
| `i`  | Norris Khan | DEF | 71 | 54.0 | 6.1 | 4.2 | 100% |
| `j`  | Ronnie Rozier | OFF | 87 | 51.7 | 9.1 | - | - |

### 11. bounce 3.2 units from the rim — same winner

window 1.57s

```
|                    
|                    
|            f       
|                    
|                    
|                    
|            e       
|        a           
|                    
|              I     
|       hi     F A   
|                    
|              CoR   
|             d      
|              b     
|                    
|        g           
|     c              
|                    
|                    
|                    
|                    
|                    
|                    
```

| | player | side | AG | composite | dist@shot | dist@arrival | got |
|---|---|---|---|---|---|---|---|
| `a`  | Kent McManus | DEF | 11 | 16.3 | 17.2 | 5.1 | 100% |
| `b`  | Benny Pena | OFF | 51 | 30.4 | 5.4 | 1.0 | 100% |
| `c`  | Cedric Buckles | OFF | 18 | 55.2 | 22.4 | 1.9 | 96% |
| `d`  | Von Sanborn | DEF | 70 | 30.0 | 4.5 | 1.0 | 100% |
| `e` BEFORE **AFTER** | CJ Castleman | DEF | 19 | 60.2 | 13.0 | 3.6 | 100% |
| `f`  | Roger Henrich | OFF | 19 | 68.0 | 20.2 | 3.2 | 100% |
| `g`  | Freddie Anderson | DEF | 24 | 58.5 | 15.7 | 0.0 | 100% |
| `h`  | Norris Khan | OFF | 51 | 42.0 | 16.5 | - | - |
| `i`  | Ronnie Rozier | DEF | 60 | 36.6 | 13.3 | 6.7 | 100% |

### 12. bounce 3.6 units from the rim — same winner

window 1.15s

```
|                    
|                    
|            a       
|                    
|                    
|                    
|     c              
|                    
|          f d       
|                    
|            C HoE   
|              I     
|         h    CDB   
|             I      
|              g e   
|                    
|           b        
|                    
|                    
|        i           
|                    
|                    
|                    
|                    
```

| | player | side | AG | composite | dist@shot | dist@arrival | got |
|---|---|---|---|---|---|---|---|
| `a`  | Xenon Fletcher | OFF | 62 | 30.4 | 17.5 | 1.6 | 78% |
| `b`  | Cedric Buckles | DEF | 25 | 71.0 | 14.4 | 3.2 | 100% |
| `c`  | Von Sanborn | OFF | 72 | 23.1 | 21.9 | 5.7 | 79% |
| `d`  | Joey Giblin | DEF | 38 | 26.4 | 7.1 | 2.0 | 100% |
| `e` BEFORE **AFTER** | Roger Henrich | DEF | 23 | 72.4 | 8.1 | 2.2 | 100% |
| `f`  | Ervin Miller | DEF | 71 | 32.7 | 11.7 | 1.4 | 100% |
| `g`  | Freddie Anderson | OFF | 25 | 61.7 | 8.2 | - | - |
| `h`  | Norris Khan | DEF | 69 | 53.7 | 12.4 | 1.0 | 100% |
| `i`  | Ronnie Rozier | OFF | 78 | 48.9 | 22.7 | 5.7 | 80% |

### 13. bounce 10.4 units from the rim — same winner

window 1.10s

```
|                    
|                    
|                    
|            c       
|                    
|                    
|                    
|       f            
|            o       
|                    
|         j  h JH    
|              C     
|           abFG E   
|              CF    
|               e    
|                    
|              i     
|                    
|         g          
|                    
|                    
|                    
|                    
|                    
```

| | player | side | AG | composite | dist@shot | dist@arrival | got |
|---|---|---|---|---|---|---|---|
| `a`  | Xenon Fletcher | OFF | 64 | 30.2 | 6.5 | - | - |
| `b`  | Benny Pena | DEF | 46 | 28.8 | 7.0 | 4.6 | 100% |
| `c`  | Omar Nola | OFF | 45 | 41.4 | 10.3 | 5.5 | 76% |
| `d`  | Cedric Buckles | DEF | 17 | 53.6 | 8.0 | 6.3 | 100% |
| `e`  | Wilbert Struthers | DEF | 71 | 56.0 | 12.3 | 8.8 | 100% |
| `f`  | Trent Athens | OFF | 58 | 35.6 | 10.4 | 7.1 | 80% |
| `g`  | Clint Workman | OFF | 67 | 38.1 | 19.5 | 7.7 | 96% |
| `h` BEFORE **AFTER** | Roger Henrich | DEF | 15 | 58.6 | 3.0 | 5.8 | 100% |
| `i`  | Freddie Anderson | OFF | 23 | 57.2 | 16.2 | 4.9 | 100% |
| `j`  | Norris Khan | DEF | 57 | 45.7 | 6.8 | 4.9 | 100% |

### 14. bounce 10.6 units from the rim — same winner

window 1.62s

```
|                    
|                    
|               h    
|                    
|                    
|                    
|                    
|                    
|               f    
|        a           
|              B     
|                    
|              E R   
|            D H     
|           G  I     
|              A     
|          i  og     
|     e        d     
|                    
|                    
|                b   
|               c    
|                    
|                    
```

| | player | side | AG | composite | dist@shot | dist@arrival | got |
|---|---|---|---|---|---|---|---|
| `a`  | Xenon Fletcher | DEF | 64 | 30.2 | 16.4 | 2.2 | 100% |
| `b`  | Omar Nola | DEF | 47 | 42.8 | 9.4 | 10.1 | 100% |
| `c`  | Cedric Buckles | OFF | 15 | 48.0 | 11.7 | - | - |
| `d` BEFORE **AFTER** | CJ Castleman | DEF | 19 | 59.4 | 3.6 | 5.1 | 100% |
| `e`  | Wilbert Struthers | OFF | 75 | 58.9 | 16.3 | 8.2 | 100% |
| `f`  | Trent Athens | DEF | 66 | 38.6 | 15.5 | 5.7 | 100% |
| `g`  | Roger Henrich | OFF | 16 | 61.0 | 2.2 | 5.0 | 100% |
| `h`  | Norris Khan | OFF | 57 | 46.0 | 27.3 | 4.3 | 95% |
| `i`  | Ronnie Rozier | DEF | 66 | 39.5 | 6.3 | 4.1 | 100% |

### 15. bounce 28.1 units from the rim — same winner

window 1.42s

```
|                    
|                    
|            f       
|                    
|        d           
|                    
|                    
|                    
|          h e D     
|              BG    
|              FgI   
|              J     
|  o           HIR   
|              C     
|            j       
|                    
|          a         
|                    
|            b       
|                    
|            i       
|                    
|                    
|                    
```

| | player | side | AG | composite | dist@shot | dist@arrival | got |
|---|---|---|---|---|---|---|---|
| `a`  | Kent McManus | OFF | 8 | 8.3 | 16.2 | - | - |
| `b`  | Cedric Buckles | DEF | 17 | 50.2 | 21.5 | 25.2 | 100% |
| `c`  | Kermit Prospect | OFF | 18 | 56.5 | 24.7 | 23.0 | 100% |
| `d`  | Von Sanborn | OFF | 64 | 20.2 | 19.7 | 24.4 | 100% |
| `e` BEFORE **AFTER** | Wilbert Struthers | DEF | 67 | 55.2 | 20.6 | 22.2 | 100% |
| `f`  | Clint Workman | OFF | 64 | 32.8 | 26.9 | 23.4 | 100% |
| `g`  | Roger Henrich | DEF | 16 | 61.0 | 25.3 | 26.0 | 100% |
| `h`  | Ervin Miller | DEF | 55 | 26.1 | 17.5 | 22.0 | 100% |
| `i`  | Freddie Anderson | OFF | 19 | 51.3 | 24.1 | 24.4 | 80% |
| `j`  | Norris Khan | DEF | 51 | 42.3 | 18.4 | 23.2 | 100% |

