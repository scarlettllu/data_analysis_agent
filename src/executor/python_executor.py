"""Safe Python execution sandbox for analysis logic."""
from __future__ import annotations

import io
import sys
import traceback
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from src.executor.sql_executor import ExecutionResult


@dataclass
class PythonResult:
    success: bool
    output: str = ""
    result: Any = None
    dataframe: pd.DataFrame | None = None
    code: str = ""
    error: str = ""
    error_hint: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class PythonExecutor:
    """Execute analysis Python code with restricted globals."""

    ALLOWED_MODULES = {"pd": pd, "np": np, "pandas": pd, "numpy": np}

    def execute(self, code: str, df: pd.DataFrame | None = None, extra: dict[str, Any] | None = None) -> PythonResult:
        stdout_capture = io.StringIO()
        local_vars: dict[str, Any] = {"df": df, "result": None}
        if extra:
            local_vars.update(extra)
        globals_safe = {"__builtins__": __builtins__, **self.ALLOWED_MODULES}

        try:
            old_stdout = sys.stdout
            sys.stdout = stdout_capture
            exec(code, globals_safe, local_vars)
            sys.stdout = old_stdout

            result = local_vars.get("result")
            out_df = None
            if isinstance(result, pd.DataFrame):
                out_df = result
            elif "df" in local_vars and isinstance(local_vars["df"], pd.DataFrame):
                out_df = local_vars["df"]

            return PythonResult(
                success=True,
                output=stdout_capture.getvalue(),
                result=result,
                dataframe=out_df,
                code=code,
            )
        except Exception as e:
            sys.stdout = sys.__stdout__
            tb = traceback.format_exc()
            return PythonResult(
                success=False,
                code=code,
                error=str(e),
                error_hint=self._explain_error(str(e)),
                output=stdout_capture.getvalue(),
                metadata={"traceback": tb},
            )

    @staticmethod
    def _explain_error(error: str) -> str:
        if "KeyError" in error:
            return "字段名不存在，请对照 schema 使用正确列名。"
        if "TypeError" in error:
            return "数据类型不匹配，可能需要 astype 转换或处理缺失值。"
        return "请检查代码逻辑和数据结构。"

    def to_execution_result(self, pr: PythonResult) -> ExecutionResult:
        return ExecutionResult(
            success=pr.success,
            data=pr.dataframe,
            sql=pr.code,
            error=pr.error,
            error_hint=pr.error_hint,
            row_count=len(pr.dataframe) if pr.dataframe is not None else 0,
            metadata={"output": pr.output, "result": pr.result},
        )
