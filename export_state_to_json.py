#!/usr/bin/env python3
"""
Export / inspect bot state in JSON format.
Makes the state file human-readable and editable.
The bot uses JSON exclusively — no pickle files are involved.
"""

from utils.state import BotState
from config import load_config

def main():
    # Load config
    config = load_config()

    print("Turtle Bot State Exporter")
    print("=" * 60)

    # Load current state from JSON
    print(f"\nLoading state from: {config.STATE_FILE}")
    state = BotState.load(config.STATE_FILE, config.ACCOUNT_SIZE)

    # State files are already JSON; derive the output path from the
    # configured STATE_FILE directly (no .pkl -> .json replacement needed).
    json_file = config.STATE_FILE
    if not json_file.endswith('.json'):
        json_file = json_file.rsplit('.', 1)[0] + '.json'

    # Save to JSON
    print(f"Saving to JSON: {json_file}")
    state.save(json_file)

    # Display summary
    print("\nExport complete!")
    print("\nState Summary:")
    print(f"  - Current Equity: ${state.current_equity:,.2f}")
    print(f"  - Initial Equity: ${state.initial_equity:,.2f}")
    print(f"  - Total P&L: ${state.total_pnl:,.2f}")
    print(f"  - Active Positions: {len(state.active_positions)}")
    print(f"  - Closed Positions: {len(state.closed_positions)}")
    print(f"  - Total Trades: {state.total_trades}")
    print(f"  - Win Rate: {state.get_summary()['win_rate'] * 100:.1f}%")
    print(f"  - Max Drawdown: {state.max_drawdown * 100:.2f}%")

    if state.active_positions:
        print("\nActive Positions:")
        for symbol, pos in state.active_positions.items():
            print(f"  - {symbol}: System {pos.system}, {pos.unit_count} units, ${pos.unrealized_pnl:,.2f} P&L")

    print(f"\nYou can now edit: {json_file}")
    print("   The bot will automatically load from JSON on next run!")
    print("=" * 60)

if __name__ == '__main__':
    main()
