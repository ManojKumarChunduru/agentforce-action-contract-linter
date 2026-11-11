/**
 * Looks up shipment tracking for an order. The Track_Shipment action points at
 * ShipmentTrackerV2, which was never written; this class is the one that exists.
 */
public with sharing class ShipmentTracker {

    public class Request {
        @InvocableVariable(required=true label='Order Number')
        public String orderNumber;
    }

    public class Response {
        @InvocableVariable(label='Tracking Status')
        public String trackingStatus;
        @InvocableVariable(label='Carrier')
        public String carrier;
    }

    @InvocableMethod(label='Track Shipment')
    public static List<Response> track(List<Request> requests) {
        List<Response> out = new List<Response>();
        for (Request r : requests) {
            Response resp = new Response();
            resp.trackingStatus = 'In transit';
            resp.carrier = 'Unknown';
            out.add(resp);
        }
        return out;
    }
}
