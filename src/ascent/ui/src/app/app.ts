import { Component } from '@angular/core';
import { Toast } from 'primeng/toast';
import { ConfirmDialog } from 'primeng/confirmdialog';
import { AppShellComponent } from './components/shell/app-shell.component';

@Component({
  selector: 'app-root',
  imports: [AppShellComponent, Toast, ConfirmDialog],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {}
