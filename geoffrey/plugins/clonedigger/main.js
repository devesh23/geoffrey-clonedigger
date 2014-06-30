$(function() {

   window.app.subscribe(
       'clonedigger',  // The name of this subscription.
       {  // The subscription criteria.
        'project': project_id,  // Global variable `project_id`
        'plugin': 'clonedigger'
       },
       function(data) {
         // This callback is called when an event that match with this
         // subscription arrives.
         console.dir(data)
       }
   );

});