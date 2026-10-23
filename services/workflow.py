def can_create_pickup(donation_status, ngo_accepted, location_confirmed):
    return (
        donation_status == "NGO_ACCEPTED"
        and ngo_accepted
        and location_confirmed
    )
