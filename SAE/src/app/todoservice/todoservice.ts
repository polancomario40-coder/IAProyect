import { Injectable } from '@angular/core';
import {Http,RequestOptions,Headers} from '@angular/http';
import 'rxjs/add/operator/toPromise';
import {TodoListComponent} from '../todolist/todolist';


@Injectable()

export class TodoService {
 


 constructor(private http:Http){

  }


getCuadre(desde:Date,hasta:Date, usuario:string, sucursal:string): Promise<any>{
   
   
    return this.http.get(`http://localhost:62313/api/Cuadre/?desde=${desde}&hasta=${hasta}&usuario=${usuario}&sucursal=${sucursal}`)
    .toPromise()
   .then(data=>{ 
      return data.json();
      
     //console.log(this.Todolist);
    })
  }

  getListSucursales(): Promise<any>{

    return this.http.get(`http://localhost:62313/api/list`)
    .toPromise()
    .then(data=>{ 
     return data.json();
    
      
   })
  }

   
  getListUsuario(): Promise<any>{

    return this.http.get(`http://localhost:62313/api/cuadre`)
    .toPromise()
    .then(data=>{ 
     return data.json();
    
      
   })
  }

  getCuadrePDF(desde:Date,hasta:Date, usuario:string, sucursal:string): void {
      
      
        window.open(`http://localhost:62313/api/Cuadrepdf/?desde=${desde}&hasta=${hasta}&usuario=${usuario}&sucursal=${sucursal}`);
     
      }
  
  
}



