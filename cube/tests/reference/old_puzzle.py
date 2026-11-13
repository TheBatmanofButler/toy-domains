"""Generic sticker-permutation puzzle engine (n x n x n cube, n in {2,3}).

The SAME code (h, G_k tied-best sets, horizon, chain scoring, valid-sequence enumeration) is exercised on the 2x2x2
(against the exhaustive distance table) and used on the 3x3x3.

State = numpy uint8 array of length n_stickers; entry = index of the face (0..5 in order U R F D L B) whose centre
colour that sticker has. For 3x3 the layout is the Kociemba facelet order (U1..U9,R1..,F1..,D1..,L1..,B1..).
A move is a source permutation `src`: new_state = state[src]  (sticker at position j after the move came from src[j]).
"""
from __future__ import annotations

import itertools
import numpy as np

FACES = "URFDLB"
FACE_NORMAL = {"U": (0, 1, 0), "R": (1, 0, 0), "F": (0, 0, 1), "D": (0, -1, 0), "L": (-1, 0, 0), "B": (0, 0, -1)}
TURNS = ("", "'", "2")


def _sticker_pos(face: str, i: int, n: int):
    """3D integer-ish position (x,y,z) of sticker i of a face; coordinates in units where cubie centres are
    at odd/even offsets: for n=3 in {-1,0,1}, for n=2 in {-1,+1}. Kociemba reading order."""
    r, c = divmod(i, n)
    if n == 3:
        a, b = r - 1, c - 1  # -1..1
        ra, rb = 1 - r, 1 - c
    else:
        a, b = (-1 if r == 0 else 1), (-1 if c == 0 else 1)
        ra, rb = -a, -b
    if face == "U":   # row 0 = back (z=-1), col 0 = left (x=-1)
        return (b, 1, a)
    if face == "R":   # row 0 = top, col 0 = front (z=+1)
        return (1, ra, rb)
    if face == "F":   # row 0 = top, col 0 = left
        return (b, ra, 1)
    if face == "D":   # row 0 = front (z=+1), col 0 = left
        return (b, -1, ra)
    if face == "L":   # row 0 = top, col 0 = back (z=-1)
        return (-1, ra, b)
    if face == "B":   # row 0 = top, col 0 = right (x=+1)
        return (rb, ra, -1)
    raise ValueError(face)


def _rot_about(axis, cw_from_outside=True):
    """Integer rotation matrix: clockwise quarter turn when looking at the face whose outward normal is `axis`."""
    ax = np.array(axis)
    # counter-clockwise by +90deg about ax (right-hand rule, viewed from tip) ; clockwise viewed from outside = -90deg
    k = ax
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    # 90deg: R = I + sin K + (1-cos) K^2 = I + K + K^2
    Rccw = np.eye(3, dtype=int) + K + K @ K
    return np.round(Rccw.T if cw_from_outside else Rccw).astype(int)  # cw = rotation by -90


class Puzzle:
    def __init__(self, n: int, faces: str, name: str):
        self.n = n
        self.name = name
        self.N = 6 * n * n
        self.pos = {}  # (pos, normal) -> sticker index
        self.stk = []  # sticker index -> (pos tuple, normal tuple)
        for fi, f in enumerate(FACES):
            for i in range(n * n):
                p = _sticker_pos(f, i, n)
                self.stk.append((p, FACE_NORMAL[f]))
                self.pos[(p, FACE_NORMAL[f])] = len(self.stk) - 1
        assert len(self.pos) == self.N
        self.solved = np.repeat(np.arange(6, dtype=np.uint8), n * n)
        # moves
        self.move_names, self.move_face, self.move_src = [], [], []
        for f in faces:
            R = _rot_about(FACE_NORMAL[f])
            ax = np.array(FACE_NORMAL[f])
            src1 = np.arange(self.N)
            def layer(p):
                return np.dot(ax, p) > 0  # outer layer on that face (n=3: coord 1; n=2: coord +1)
            for i, (p, nrm) in enumerate(self.stk):
                if layer(p):
                    q = tuple(int(x) for x in R @ np.array(p))
                    m = tuple(int(x) for x in R @ np.array(nrm))
                    src1[self.pos[(q, m)]] = i
            p2 = src1[src1]
            p3 = src1[p2]
            # clockwise = src1 ; counter-clockwise = src1^3 ; half = src1^2
            for t, perm in (("", src1), ("'", p3), ("2", p2)):
                self.move_names.append(f + t)
                self.move_face.append(FACES.index(f))
                self.move_src.append(perm.copy())
        self.M = len(self.move_names)
        self.src = np.array(self.move_src)            # (M, N)
        self.face = np.array(self.move_face)          # (M,)
        self.mi = {m: i for i, m in enumerate(self.move_names)}
        self.inv_move = np.array([self.mi[_inv_name(m)] for m in self.move_names])
        # piece incidence for h : pieces = positions (cubies) other than centres
        cub = {}
        for i, (p, nrm) in enumerate(self.stk):
            nz = sum(1 for x in p if x != 0)
            if nz >= 2:
                cub.setdefault(p, []).append(i)
        self.pieces = [v for k, v in sorted(cub.items())]
        self.n_pieces = len(self.pieces)
        self.noncenter = np.array([i for i in range(self.N) if sum(1 for x in self.stk[i][0] if x != 0) >= 2])
        A = np.zeros((self.N, self.n_pieces + 1), np.float32)
        for k, v in enumerate(self.pieces):
            A[v, k] = 1
        A[self.noncenter, self.n_pieces] = 1
        self._A = A
        self._psize = np.array([len(v) for v in self.pieces] + [0], np.float32)
        self._build_paths()

    # -------------------------------------------------------------- paths
    def _build_paths(self):
        """valid k-paths (no two consecutive moves on the same face), k = 1..3 ; composite source permutations."""
        self.paths = {}
        self.path_src = {}
        self.path_first = {}
        cur = [(m,) for m in range(self.M)]
        for k in (1, 2, 3):
            if k > 1:
                cur = [p + (m,) for p in cur for m in range(self.M) if self.face[m] != self.face[p[-1]]]
            self.paths[k] = np.array(cur, dtype=np.int16)
            srcs = []
            for p in cur:
                s = np.arange(self.N)
                for m in p:       # state after p: apply moves in order; s_after = s0[comp] with comp = comp[src_m]
                    s = s[self.src[m]]
                srcs.append(s)
            self.path_src[k] = np.array(srcs, dtype=np.int32)
            self.path_first[k] = self.paths[k][:, 0].astype(np.int64)

    # -------------------------------------------------------------- basics
    def apply(self, s: np.ndarray, seq) -> np.ndarray:
        for m in seq:
            m = self.mi[m] if isinstance(m, str) else m
            s = s[..., self.src[m]]
        return s

    def parse_seq(self, seq):
        return seq.split() if isinstance(seq, str) else list(seq)

    def valid_seq(self, seq) -> bool:
        idx = [self.mi[m] if isinstance(m, str) else m for m in self.parse_seq(seq)]
        return all(self.face[a] != self.face[b] for a, b in zip(idx, idx[1:]))

    def random_walk(self, length: int, rng) -> list:
        seq, last = [], -1
        for _ in range(length):
            while True:
                m = int(rng.integers(self.M))
                if self.face[m] != last:
                    break
            seq.append(m)
            last = self.face[m]
        return seq

    def valid_next(self, last_move: int):
        return [m for m in range(self.M) if last_move < 0 or self.face[m] != self.face[last_move]]

    # -------------------------------------------------------------- h
    def h_batch(self, S: np.ndarray):
        """S (..., N) uint8 -> (pieces_solved, stickers_solved) int arrays. Lexicographic pair."""
        eq = (S == self.solved).astype(np.float32)
        r = eq.reshape(-1, self.N) @ self._A
        pieces = (r[:, :self.n_pieces] == self._psize[:self.n_pieces]).sum(1)
        stick = r[:, self.n_pieces].astype(np.int64)
        sh = S.shape[:-1]
        return pieces.reshape(sh).astype(np.int64), stick.reshape(sh)

    def h(self, s):
        p, t = self.h_batch(np.asarray(s))
        return int(p), int(t)

    def hscalar(self, S):
        p, t = self.h_batch(S)
        return p * 1000 + t

    def is_solved(self, s):
        return bool((np.asarray(s) == self.solved).all())

    # -------------------------------------------------------------- G_k
    def leaf_h(self, states: np.ndarray, k: int) -> np.ndarray:
        """states (B, N) -> scalar h (pieces*1000+stickers) at the leaves of all valid k-paths: (B, n_paths)."""
        out = np.empty((states.shape[0], len(self.paths[k])), np.int64)
        ps = self.path_src[k]
        step = max(1, 400000 // (len(ps) * 1))
        for a in range(0, states.shape[0], step):
            leaves = states[a:a + step][:, ps]          # (b, P, N)
            out[a:a + step] = self.hscalar(leaves)
        return out

    def tied_best_paths(self, states, k):
        """bool (B, n_paths): the k-paths attaining the max leaf h (no solver calls)."""
        lh = self.leaf_h(np.atleast_2d(states), k)
        return lh == lh.max(1, keepdims=True)

    def tied_best_first(self, states, k):
        """bool (B, M): T_k = DISTINCT first moves of the max-leaf-h k-paths."""
        tb = self.tied_best_paths(states, k)
        first = self.path_first[k]
        T = np.zeros((tb.shape[0], self.M), bool)
        for m in range(self.M):
            T[:, m] = tb[:, first == m].any(1)
        return T

    @staticmethod
    def score_set(T: np.ndarray, Mstar: np.ndarray) -> np.ndarray:
        """|T ∩ M*| / |T| per row. T, Mstar bool (B, M)."""
        return (T & Mstar).sum(1) / T.sum(1)

    def horizon(self, states, Mstar, strict=False):
        """returns array of horizons (1,2,3 or 4 meaning '4+') and the (B,3) score matrix."""
        states = np.atleast_2d(states)
        sc = np.stack([self.score_set(self.tied_best_first(states, k), Mstar) for k in (1, 2, 3)], 1)
        ok = (sc >= 1.0 - 1e-12) if strict else (sc >= 0.5)
        hz = np.where(ok.any(1), ok.argmax(1) + 1, 4)
        return hz, sc

    # -------------------------------------------------------------- chains
    def chain_seq_valid(self, seq):
        return self.valid_seq(seq)

    def chain_score_gk(self, states, k, live_fn):
        """G_k-chain: fraction of the tied-best k-paths that are chain-live. live_fn(state, path_tuple)->bool."""
        tb = self.tied_best_paths(states, k)
        out = []
        for i, s in enumerate(np.atleast_2d(states)):
            idx = np.nonzero(tb[i])[0]
            out.append(np.mean([live_fn(s, tuple(self.paths[k][j])) for j in idx]))
        return np.array(out)


def _inv_name(m: str) -> str:
    return m[0] + {"": "'", "'": "", "2": "2"}[m[1:]]


def str_to_state(P: Puzzle, s: str) -> np.ndarray:
    return np.array([FACES.index(c) for c in s], np.uint8)


def state_to_str(P: Puzzle, a) -> str:
    return "".join(FACES[i] for i in a)


CUBE3 = Puzzle(3, "UDRLFB", "3x3")
CUBE2 = Puzzle(2, "URF", "2x2")
