import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpModule } from '@angular/http';
import { AppComponent } from './app.component';
import { RouterModule }   from '@angular/router';
import { DashboardComponent } from './dashboard/dashboard';
import { TodoListComponent } from './todolist/todolist';
import { TodoService } from './todoservice/todoservice';
import { Cuadre } from './todoservice/cuadre.model';
import { lsSucursales } from './todoservice/sucursales.model';
import { lusuario } from './todoservice/usuarios.model';
import { TodoGuardarComponent } from './todoguardar/todoguardar';

@NgModule({
  declarations: [
    AppComponent,
    DashboardComponent,
    TodoListComponent,
    TodoGuardarComponent,
    
   
  ],
  imports: [
    BrowserModule,
    FormsModule,
    HttpModule,
    RouterModule.forRoot([
      { 
        path: '',
        redirectTo: '/dashboard',
        pathMatch: 'full'
      } ,
      { 
        path: 'dashboard',
        component: DashboardComponent
      } ,
      { 
        path: 'todolist',
        component: TodoListComponent
      },
      { 
        path: 'todoguardar',
        component: TodoGuardarComponent
      },
     
     

    ])
  ],
  providers: [TodoService],
  bootstrap: [AppComponent]
})
export class AppModule { }
