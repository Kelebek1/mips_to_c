from typing import List, Optional, Tuple

from .flow_graph import (
    BasicNode,
    ConditionalNode,
    FlowGraph,
    Node,
    compute_relations,
)
from .parse_instruction import Instruction


def replace_node_references(
    flow_graph: FlowGraph, replace_this: Node, with_this: Node
) -> None:
    for node_to_modify in flow_graph.nodes:
        node_to_modify.replace_any_children(replace_this, with_this)


def remove_node(flow_graph: FlowGraph, to_delete: Node, new_child: Node) -> None:
    flow_graph.nodes.remove(to_delete)
    replace_node_references(flow_graph, to_delete, new_child)


def replace_node(flow_graph: FlowGraph, replace_this: Node, with_this: Node) -> None:
    replacement_index = flow_graph.nodes.index(replace_this)
    flow_graph.nodes[replacement_index] = with_this
    replace_node_references(flow_graph, replace_this, with_this)


def match_nodes(start: ConditionalNode) -> Optional[Tuple[Node, ...]]:
    node_1 = start.fallthrough_edge
    node_7 = start.conditional_edge

    if not isinstance(node_1, ConditionalNode):
        return None
    node_2 = node_1.fallthrough_edge
    node_5 = node_1.conditional_edge

    if not isinstance(node_2, BasicNode):
        return None
    node_3 = node_2.successor

    if not (
        isinstance(node_3, ConditionalNode)
        and node_3.loop
        and node_3.conditional_edge is node_3
    ):
        return None
    node_4 = node_3.fallthrough_edge

    if not (
        isinstance(node_4, ConditionalNode)
        and node_4.fallthrough_edge is node_5
        and node_4.conditional_edge is node_7
    ):
        return None

    if not isinstance(node_5, BasicNode):
        return None
    node_6 = node_5.successor

    if not (
        isinstance(node_6, ConditionalNode)
        and node_6.loop
        and node_6.conditional_edge is node_6
        and node_6.fallthrough_edge is node_7
    ):
        return None
    return (node_1, node_2, node_3, node_4, node_5, node_6, node_7)


def reroll_loop(flow_graph: FlowGraph, start: ConditionalNode) -> bool:
    nodes = match_nodes(start)
    if nodes is None:
        return False
    (node_1, node_2, node_3, node_4, node_5, node_6, node_7) = nodes

    def modify_node_1_instructions(instructions: List[Instruction]) -> bool:
        # First, we check that the node has the instructions we
        # think it has.
        branches = [instr for instr in instructions if instr.is_branch_instruction()]
        if len(branches) != 1:
            return False
        andi_instrs = [instr for instr in instructions if instr.mnemonic == "andi"]
        if len(andi_instrs) != 1:
            return False
        # We are now free to modify the instructions, as we have verified
        # that this node fits the criteria.
        instructions.remove(branches[0])
        andi = andi_instrs[0]
        move = Instruction.derived("move", [andi.args[0], andi.args[1]], andi)
        instructions[instructions.index(andi)] = move
        return True

    if not modify_node_1_instructions(node_1.block.instructions):
        return False

    new_node_1 = BasicNode(node_1.block, node_1.emit_goto, node_2)
    replace_node(flow_graph, node_1, new_node_1)
    remove_node(flow_graph, node_4, node_7)
    remove_node(flow_graph, node_5, node_7)
    remove_node(flow_graph, node_6, node_7)  # TODO: assert didn't execute anything?.

    return True


def reroll_loops(flow_graph: FlowGraph) -> FlowGraph:
    changed: bool = True
    while changed:
        changed = False
        for node in flow_graph.nodes:
            if not isinstance(node, ConditionalNode):
                continue
            changed = reroll_loop(flow_graph, node)
            if changed:
                compute_relations(flow_graph.nodes)
                break
    return flow_graph
