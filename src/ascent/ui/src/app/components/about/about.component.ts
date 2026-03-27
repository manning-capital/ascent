import { Component } from '@angular/core';

@Component({
  selector: 'app-about',
  standalone: true,
  template: `
    <div class="p-6 max-w-3xl mx-auto">
      <h1 class="text-2xl font-bold mb-6">About Ascent</h1>

      <div class="rounded-xl border border-edge bg-surface/50 p-6 space-y-4">
        <p class="text-fg leading-relaxed">
          Ascent is a quantitative trading platform for developing, testing, and deploying
          algorithmic trading strategies. It provides a comprehensive framework for managing
          the full lifecycle of trades from signal generation to execution and analysis.
        </p>

        <h2 class="text-lg font-semibold mt-6">Features</h2>
        <ul class="list-disc list-inside text-fg-muted space-y-2">
          <li>Multi-asset strategy support (pairs trading, momentum, mean reversion)</li>
          <li>Paper and live trading modes</li>
          <li>Real-time trade monitoring and analytics</li>
          <li>Multi-leg trade support for complex strategies</li>
          <li>Portfolio position tracking and P&L calculation</li>
          <li>Order lifecycle management</li>
          <li>Strategy condition visualization</li>
        </ul>

        <h2 class="text-lg font-semibold mt-6">Tech Stack</h2>
        <div class="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p class="text-fg-faint mb-1">Backend</p>
            <p class="text-fg">Python, FastAPI, SQLAlchemy, PostgreSQL</p>
          </div>
          <div>
            <p class="text-fg-faint mb-1">Frontend</p>
            <p class="text-fg">Angular, Tailwind CSS, Chart.js</p>
          </div>
          <div>
            <p class="text-fg-faint mb-1">Data</p>
            <p class="text-fg">Pandas, NumPy</p>
          </div>
        </div>
      </div>
    </div>
  `,
})
export class AboutComponent {}
