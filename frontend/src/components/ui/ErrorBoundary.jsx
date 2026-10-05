import React from 'react';

// Contains a render/effect crash inside one panel so it can't unmount the
// whole app (React unmounts the entire tree on an uncaught error, which
// shows as a blank black screen). The rest of the dashboard keeps working.
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error(`${this.props.label || 'Panel'} crashed:`, error, info?.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="w-full h-full min-h-[200px] flex flex-col items-center justify-center gap-3 rounded-xl border border-[#332E29] bg-[#171513] p-6 text-center">
        <div className="text-sm font-semibold text-gray-200">
          {this.props.label || 'This panel'} hit a problem
        </div>
        <p className="text-xs text-gray-400 max-w-xs">
          The rest of the dashboard is still working. Try again to reload this panel.
        </p>
        <button
          onClick={() => this.setState({ error: null })}
          className="px-3 py-1.5 rounded border border-[#3A342E] bg-[#26221D] text-xs font-mono text-gray-200 hover:border-[#C6602E]"
        >
          Retry
        </button>
      </div>
    );
  }
}
