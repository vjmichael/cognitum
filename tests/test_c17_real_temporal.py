"""C17 real-source ingestion contract; synthetic fixture only in CI."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.c17_real_temporal_acceptance import run,read_source


def write_fixture(path):
    lines=["time_ms,value,source_id,observation_id\n"]
    for i in range(60):
        lines.append(f"{i*1000},{10+i*.05:.6f},test_sensor,ob_{i}\n")
    path.write_text("".join(lines))


class C17RealSourceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:import sklearn,scipy,numpy
        except ImportError:raise unittest.SkipTest("optional native temporal backend not installed")

    def test_typed_real_source_gate_and_genuine_heldout(self):
        with TemporaryDirectory() as tmp:
            data=Path(tmp)/"temperature.csv"
            write_fixture(data)
            with self.assertRaises(PermissionError):
                run(data,train_count=40,origin_id="test",unit="celsius")
            result=run(data,train_count=40,origin_id="test",unit="celsius",
                       admitted_by_trusted_host=True)
            self.assertEqual(result["heldout_count"],20)
            self.assertEqual({x["model"] for x in result["metrics"]},
                             {"last_value","kalman","ridge_ar"})
            self.assertEqual(len(result["source_sha256"]),64)
            self.assertNotIn("test_sensor",str(result))

    def test_untrusted_file_symlink_and_duplicated_observation_refused(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            data=root/"measurements.csv"
            write_fixture(data)
            duplicate=data.read_text().replace("ob_4\n","ob_3\n")
            data.write_text(duplicate)
            with self.assertRaises(ValueError):
                run(data,train_count=40,origin_id="test",unit="celsius",
                    admitted_by_trusted_host=True)
            write_fixture(data)
            alias=root/"alias.csv"
            try:
                alias.symlink_to(data)
            except (OSError,NotImplementedError):
                # Windows CI may not grant symlink-creation privileges;
                # direct source integrity and duplicate-lineage checks still ran.
                pass
            else:
                with self.assertRaises(ValueError):
                    read_source(alias,origin_id="test",unit="celsius")

    def test_irregular_and_nonfinite_csv_are_refused(self):
        with TemporaryDirectory() as tmp:
            data=Path(tmp)/"series.csv"
            write_fixture(data)
            data.write_text(data.read_text().replace("15000,10.750000","15500,10.750000"))
            with self.assertRaises(ValueError):
                run(data,train_count=40,origin_id="test",unit="celsius",
                    admitted_by_trusted_host=True)
            write_fixture(data)
            data.write_text(data.read_text().replace("10.750000","NaN"))
            with self.assertRaises(ValueError):
                run(data,train_count=40,origin_id="test",unit="celsius",
                    admitted_by_trusted_host=True)


if __name__=="__main__":
    unittest.main()
