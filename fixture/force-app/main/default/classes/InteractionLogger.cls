/**
 * Logs a customer interaction against a contact. Invoked by the Log_Interaction action.
 * The channel is required because an interaction with no channel cannot be reported on.
 */
public with sharing class InteractionLogger {

    public class Request {
        @InvocableVariable(required=true label='Contact Id')
        public Id contactId;
        @InvocableVariable(required=true label='Channel' description='Chat, Email, Phone or Web')
        public String channel;
        @InvocableVariable(label='Notes')
        public String notes;
    }

    public class Response {
        @InvocableVariable(label='Interaction Id')
        public Id interactionId;
    }

    @InvocableMethod(label='Log Interaction')
    public static List<Response> log(List<Request> requests) {
        List<Task> tasks = new List<Task>();
        for (Request r : requests) {
            tasks.add(new Task(
                WhoId = r.contactId,
                Subject = 'Interaction via ' + r.channel,
                Description = r.notes,
                Status = 'Completed'
            ));
        }
        insert tasks;
        List<Response> out = new List<Response>();
        for (Task t : tasks) {
            Response resp = new Response();
            resp.interactionId = t.Id;
            out.add(resp);
        }
        return out;
    }
}
