using System;
using System.Collections.Generic;
using System.Data.Entity.Core.Objects;
using System.Linq;
using System.Web;
using System.Web.Mvc;
using SAEExpress.Models;

namespace SAEExpress.Controllers
{
    public class CuadreController : Controller
    {

        DBSAEExpress db = new DBSAEExpress();
        public DateTime textdesde { get; set; }
        public DateTime texthasta { get; set; }
        public string Sucursal {get; set;}
        public string Usuario { get; set; }

        // GET: Cuadre
        public ActionResult Index()
        {
            return View();
        }


        public ActionResult ViewAll()
        {
            return View(GetAllCuadre(Request.Form["textdesde"], Request.Form["texthasta"]));
        }

        IEnumerable<spCuadre> GetAllCuadre(string desde, string hasta)
        {

           var lista = db.GetCuadre(DateTime.Parse(desde),DateTime.Parse(hasta),Usuario,Sucursal).ToList();
            return lista;
        }

        
    }
}