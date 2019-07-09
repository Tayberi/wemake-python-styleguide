# -*- coding: utf-8 -*-

import ast
from typing import ClassVar, List

import astor
from typing_extensions import final

from wemake_python_styleguide.types import AnyNodes
from wemake_python_styleguide.violations.best_practices import (
    MultilineConditionsViolation,
    NegatedConditionsViolation,
    SameElementsInConditionViolation,
    UselessReturningElseViolation,
)
from wemake_python_styleguide.visitors.base import BaseNodeVisitor


@final
class IfStatementVisitor(BaseNodeVisitor):
    """Checks single and consecutive ``if`` statement nodes."""

    #: Nodes that break or return the execution flow.
    _returning_nodes: ClassVar[AnyNodes] = (
        ast.Break,
        ast.Raise,
        ast.Return,
    )

    def _check_negated_conditions(self, node: ast.If) -> None:
        if not node.orelse:
            return

        if isinstance(node.test, ast.UnaryOp):
            if isinstance(node.test.op, ast.Not):
                self.add_violation(NegatedConditionsViolation(node))
        elif isinstance(node.test, ast.Compare):
            if any(isinstance(elem, ast.NotEq) for elem in node.test.ops):
                self.add_violation(NegatedConditionsViolation(node))

    def _check_multiline_conditions(self, node: ast.If) -> None:
        """Checks multiline conditions ``if`` statement nodes."""
        start_lineno = getattr(node, 'lineno', None)
        for sub_nodes in ast.walk(node.test):
            sub_lineno = getattr(sub_nodes, 'lineno', None)
            if sub_lineno is not None and sub_lineno > start_lineno:
                self.add_violation(MultilineConditionsViolation(node))
                break

    def _check_useless_else(self, node: ast.If) -> None:
        if not node.orelse:
            return

        next_chain = getattr(node, 'wps_chain', None)  # TODO: move into utils
        has_previous_chain = getattr(node, 'wps_chained', None)
        if next_chain or has_previous_chain:
            return

        if any(isinstance(line, self._returning_nodes) for line in node.body):
            self.add_violation(UselessReturningElseViolation(node))

    def visit_If(self, node: ast.If) -> None:
        """
        Checks ``if`` nodes.

        Raises:
            UselessReturningElseViolation
            NegatedConditionsViolation
            MultilineConditionsViolation

        """
        self._check_negated_conditions(node)
        self._check_useless_else(node)
        self._check_multiline_conditions(node)
        self.generic_visit(node)


@final
class BooleanConditionVisitor(BaseNodeVisitor):
    """Ensures that boolean conditions are correct."""

    def _get_all_names(
        self,
        node: ast.BoolOp,
    ) -> List[str]:
        # That's an ugly hack to make sure that we do not visit
        # one chained `BoolOp` elements twice. Sorry!
        node._wps_visited = True  # type: ignore  # noqa: Z441

        names = []
        for operand in node.values:
            if isinstance(operand, ast.BoolOp):
                names.extend(self._get_all_names(operand))
            else:
                names.append(astor.to_source(operand))
        return names

    def _check_same_elements(self, node: ast.BoolOp) -> None:
        if getattr(node, '_wps_visited', False):  # noqa: Z425
            return  # We do not visit nested `BoolOp`s twice.

        operands = self._get_all_names(node)
        if len(set(operands)) != len(operands):
            self.add_violation(SameElementsInConditionViolation(node))

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        """
        Checks that ``and`` and ``or`` conditions are correct.

        Raises:
            SameElementsInConditionViolation

        """
        self._check_same_elements(node)
        self.generic_visit(node)
