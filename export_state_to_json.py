#!/usr/bin/env python3
"""
Export bot state from pickle to JSON format
Makes the state file human-readable and editable
"""

from utils.state import BotState
from config import load_config

def main():
    # Load config
    config = load_config()

    print("🐢 Turtle Bot State Exporter")
    print("=" * 60)

    # Load current state from pickle
    print(f"\n📂 Loading state from: {config.STATE_FILE}")
    state = BotState.load(config.STATE_FILE, config.ACCOUNT_SIZE)

    # Generate JSON filename
    json_file = config.STATE_FILE.replace('.pkl', '.json')

    # Save to JSON
    print(f"💾 Exporting to JSON: {json_file}")
    state.save_json(json_file)

    # Display summary
    print("\n✅ Export complete!")
    print("\n📊 State Summary:")
    print(f"  - Current Equity: ${state.current_equity:,.2f}")
    print(f"  - Initial Equity: ${state.initial_equity:,.2f}")
    print(f"  - Total P&L: ${state.total_pnl:,.2f}")
    print(f"  - Active Positions: {len(state.active_positions)}")
    print(f"  - Closed Positions: {len(state.closed_positions)}")
    print(f"  - Total Trades: {state.total_trades}")
    print(f"  - Win Rate: {state.get_summary()['win_rate']:.1f}%")
    print(f"  - Max Drawdown: {state.max_drawdown * 100:.2f}%")

    if state.active_positions:
        print("\n🔵 Active Positions:")
        for symbol, pos in state.active_positions.items():
            print(f"  - {symbol}: System {pos.system}, {pos.unit_count} units, ${pos.unrealized_pnl:,.2f} P&L")

    print(f"\n📝 You can now edit: {json_file}")
    print("   The bot will automatically load from JSON on next run!")
    print("=" * 60)

if __name__ == '__main__':
    main()
