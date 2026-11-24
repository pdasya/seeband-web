import runpy
import unittest
from pathlib import Path

DRIVER = (
    Path(__file__).resolve().parents[3]
    / "docs/superpowers/specs/band-composition-v0.7/evidence/replay_p18.py"
)


class ExpectedFailureContract(unittest.TestCase):
    def test_only_the_documented_numerical_failure_is_accepted(self):
        validate = runpy.run_path(str(DRIVER))["validate_old_hall"]
        documented = (
            "CB+CB dis 800 K: R_H [m^3/C], oracle [m^3/C], scaled error "
            "-7.038047601642028e-06 -7.038039355547361e-06 1.1716465694490075e-06\n"
            "AssertionError: DPB-HALL design budget exceeded: 1.17164656945e-06 >= 1e-6\n"
        )
        validate(1, documented, 1.1716465694490075e-6)
        for code, output in [
            (0, documented),
            (1, "ImportError: missing core"),
            (1, documented.replace("1.1716465694490075e-06", "nan")),
        ]:
            with self.subTest(code=code, output=output):
                with self.assertRaises(RuntimeError):
                    validate(code, output, 1.1716465694490075e-6)


if __name__ == "__main__":
    unittest.main()
