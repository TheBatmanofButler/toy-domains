"""Prompt-visible state features used by L' (brief 4d) and reported per pool. Everything is computed from the facelet
array alone (no d, no horizon, no M*). Works for any rk.puzzle.Puzzle; features that do not exist on a puzzle
(edges / cross on 2x2) are identically 0.

State-level features (per state), in this order (see STATE_FEATURES):
  pieces_solved, stickers_solved            h = (pieces, stickers)
  face_solved[6]                            solved non-centre stickers per face (U R F D L B)
  corners_solved, edges_solved
  corner_twist                              number of corners with non-zero orientation (as read from the facelets)
  edge_flip                                 number of flipped edges (Kociemba/F-B convention, see _edge_flip)
  cross[6]                                  1 if the 4 edges touching that face's centre are all solved (3x3 only)
Pair features for (state, move): state features of s, of s*m, their differences, move-face one-hot (6), turn one-hot (3).
"""
from __future__ import annotations

import numpy as np
from old_puzzle import Puzzle, FACES

STATE_FEATURES = (["pieces", "stickers"] + [f"face_{f}" for f in FACES] + ["corners", "edges", "twist", "flip"]
                  + [f"cross_{f}" for f in FACES])


class FeatureExtractor:
    def __init__(self, P: Puzzle):
        self.P = P
        pos_of = {}
        for k, st in enumerate(P.pieces):
            pos_of[k] = st
        self.corner_ids = [k for k, st in enumerate(P.pieces) if len(st) == 3]
        self.edge_ids = [k for k, st in enumerate(P.pieces) if len(st) == 2]
        # face -> non-centre sticker index lists
        self.face_idx = [[i for i in range(P.N) if i // (P.n ** 2) == f and i in set(P.noncenter.tolist())] for f in range(6)]
        # corner slot-0 sticker: the one lying on a U/D face (normal y != 0)
        self.corner_ref = []
        for k in self.corner_ids:
            st = P.pieces[k]
            self.corner_ref.append([i for i in st if P.stk[i][1][1] != 0][0])
        # edges: reference sticker and group
        self.edge_ref, self.edge_ref_grp = [], []
        for k in self.edge_ids:
            st = P.pieces[k]
            ud = [i for i in st if P.stk[i][1][1] != 0]
            fb = [i for i in st if P.stk[i][1][2] != 0]
            self.edge_ref.append((ud or fb)[0])
        # cross: edges (piece ids) having a sticker on face f
        self.cross_edges = []
        for f in range(6):
            ids = [j for j, k in enumerate(self.edge_ids) if any(i // (P.n ** 2) == f for i in P.pieces[k])]
            self.cross_edges.append(ids)
        self.names = STATE_FEATURES

    def state_features(self, S: np.ndarray) -> np.ndarray:
        """S (B,N) -> (B, len(STATE_FEATURES)) float32."""
        P = self.P
        S = np.atleast_2d(S)
        B = S.shape[0]
        eq = (S == P.solved)
        r = eq.astype(np.float32) @ P._A
        psol = (r[:, :P.n_pieces] == P._psize[:P.n_pieces])              # (B, n_pieces) bool
        F = np.zeros((B, len(STATE_FEATURES)), np.float32)
        F[:, 0] = psol.sum(1)
        F[:, 1] = r[:, P.n_pieces]
        for f in range(6):
            F[:, 2 + f] = eq[:, self.face_idx[f]].sum(1)
        F[:, 8] = psol[:, self.corner_ids].sum(1)
        F[:, 9] = psol[:, self.edge_ids].sum(1) if self.edge_ids else 0
        # corner twist: ref sticker colour not in {U (0), D (3)}
        ref = S[:, self.corner_ref]
        F[:, 10] = ((ref != 0) & (ref != 3)).sum(1)
        # edge flip
        if self.edge_ids:
            flips = np.zeros(B)
            for j, k in enumerate(self.edge_ids):
                st = P.pieces[k]
                cols = S[:, st]
                has_ud = ((cols == 0) | (cols == 3)).any(1)
                ref_col = S[:, self.edge_ref[j]]
                good = np.where(has_ud, (ref_col == 0) | (ref_col == 3), (ref_col == 2) | (ref_col == 5))
                flips += ~good
            F[:, 11] = flips
            for f in range(6):
                F[:, 12 + f] = psol[:, [self.edge_ids[j] for j in self.cross_edges[f]]].all(1)
        return F

    def pair_features(self, S: np.ndarray, chunk: int = 20000):
        """S (B,N) -> X (B, M, nf) float32 for all moves, and the feature name list."""
        P = self.P
        S = np.atleast_2d(S)
        B = S.shape[0]
        f0 = self.state_features(S)
        nS = f0.shape[1]
        out = []
        for a in range(0, B, chunk):
            Sb = S[a:a + chunk]
            b = Sb.shape[0]
            after = Sb[:, P.src]                                           # (b, M, N)
            f1 = self.state_features(after.reshape(-1, P.N)).reshape(b, P.M, nS)
            fb = f0[a:a + chunk][:, None, :]
            mv = np.zeros((b, P.M, 6 + 3), np.float32)
            for m in range(P.M):
                mv[:, m, P.face[m]] = 1
                mv[:, m, 6 + {"": 0, "'": 1, "2": 2}[P.move_names[m][1:]]] = 1
            out.append(np.concatenate([np.broadcast_to(fb, f1.shape), f1, f1 - fb, mv], 2))
        names = ([f"before_{n}" for n in STATE_FEATURES] + [f"after_{n}" for n in STATE_FEATURES]
                 + [f"delta_{n}" for n in STATE_FEATURES] + [f"mvface_{f}" for f in FACES] + ["turn_cw", "turn_ccw", "turn_half"])
        return np.concatenate(out, 0), names
