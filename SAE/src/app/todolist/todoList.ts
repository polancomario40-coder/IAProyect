import { Component,OnInit } from '@angular/core';
import {TodoService} from '../todoservice/todoservice';
import { Cuadre } from '../todoservice/cuadre.model';
import { lsSucursales } from '../todoservice/sucursales.model';
import { lusuario } from '../todoservice/usuarios.model';

@Component({
  selector: 'todoList',
  templateUrl: './todoList.html',
  styleUrls: ['./todoList.css']


})
export class TodoListComponent implements OnInit {
  title = 'Cuadre General';
  items: Cuadre[]= [];
  vsucursales : lsSucursales[]=[]; 
  vusuario : lusuario[]=[]
  desde;
  hasta;
  id ='';
  usuario ='';
  Sucursal = '';
   


  constructor(private todoService:TodoService){}
  
    ngOnInit()
    {
      this.listSucursales();
      this.listUsuarios();
    }

    listCuadre()
    {
      
       console.log(this.desde);
       console.log(this.hasta);
       console.log(this.Sucursal);
       console.log(this.id);
       console.log(this.usuario);
       
      this.todoService.getCuadre(this.desde,this.hasta,this.id,this.Sucursal)
        .then(x => this.items = x);

    }

    listSucursales()
    {
      this.todoService.getListSucursales()
        .then((x) => {
          this.vsucursales = x;
          
         
        });

    }
         listUsuarios()
    {
      this.todoService.getListUsuario()
        .then((x) => {
          this.vusuario = x;
         
        });
    }

     CuadrePDF()
          {
                
            this.todoService.getCuadrePDF(this.desde,this.hasta,this.id,this.Sucursal);
            
          }

    }
   
    
