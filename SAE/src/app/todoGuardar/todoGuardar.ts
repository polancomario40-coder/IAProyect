import { Component } from '@angular/core';
import {TodoService} from '../todoservice/todoservice';

@Component({
  selector: 'todoGuardar',
  templateUrl: './todoGuardar.html',
  styleUrls: ['./todoGuardar.css']
})
export class TodoGuardarComponent
{
  title = 'Codigo de autorizacion';
  Carateres : any=[];
  cliente : {idCliente: string, cliente: string} = {idCliente:'1', cliente:''}

/*var randomstring = require("randomstring");


this.Carateres = randomstring.generate(7);
console.log(This.Carateres);
*/

  
 /*post()
  {
    this.todoService.post(this.cliente).then(data=>{
     console.log(data);

    })
  }  
*/
  /*getdata()
  {
    this.todoService.getdata();
    this.movie = this.todoService.movie;
  }
  constructor(public todoService:TodoService)
  {

  }
*/
}
