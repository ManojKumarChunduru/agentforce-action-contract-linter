/**
 * Updates a contact's communication preference for one channel.
 * Invoked by the Update_Contact_Preferences action. All three inputs are required:
 * the update is meaningless without a channel.
 */
public with sharing class ContactPreferenceUpdater {

    public class Request {
        @InvocableVariable(required=true label='Contact Id')
        public Id contactId;
        @InvocableVariable(required=true label='Channel' description='Email, SMS or Phone')
        public String channel;
        @InvocableVariable(required=true label='Opt In')
        public Boolean optIn;
    }

    public class Response {
        @InvocableVariable(label='Success')
        public Boolean success;
    }

    @InvocableMethod(label='Update Contact Preferences')
    public static List<Response> update(List<Request> requests) {
        List<Contact> toUpdate = new List<Contact>();
        for (Request r : requests) {
            Contact c = new Contact(Id = r.contactId);
            if (r.channel == 'Email') {
                c.HasOptedOutOfEmail = !r.optIn;
            } else if (r.channel == 'Phone') {
                c.DoNotCall = !r.optIn;
            }
            toUpdate.add(c);
        }
        update toUpdate;
        List<Response> out = new List<Response>();
        for (Request r : requests) {
            Response resp = new Response();
            resp.success = true;
            out.add(resp);
        }
        return out;
    }
}
