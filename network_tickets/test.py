import ipaddress
import math

def generate_subnet(network, num_ip_addresses, existing_subnets=None):
    """
    Generate a subnet from a given network with enough capacity for specified IPs and check for overlaps.
    
    Args:
        network (str or ipaddress.IPv4Network/IPv6Network): The parent network
        num_ip_addresses (int): Number of IP addresses needed in the new subnet
        existing_subnets (list): List of existing subnets to check against
        
    Returns:
        ipaddress.IPv4Network/IPv6Network: The generated subnet if no overlap
        None: If no valid subnet can be generated or there's an overlap
        
    Raises:
        ValueError: If input parameters are invalid
    """
    # Validate number of IP addresses
    if not isinstance(num_ip_addresses, int) or num_ip_addresses <= 0:
        raise ValueError("Number of IP addresses must be a positive integer")
        
    # Normalize input network to ipaddress object
    if isinstance(network, str):
        network = ipaddress.ip_network(network, strict=False)
    elif not isinstance(network, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
        raise ValueError("Invalid network format. Provide a string or ipaddress Network object.")
    
    # Calculate required prefix length
    # We need to account for network and broadcast addresses in IPv4 (hence +2)
    if isinstance(network, ipaddress.IPv4Network):
        required_hosts = num_ip_addresses + 2  # +2 for network and broadcast addresses
    else:  # IPv6 doesn't use broadcast addresses
        required_hosts = num_ip_addresses
    
    # Calculate minimum prefix length needed
    if required_hosts <= 1:
        prefix_length = network.max_prefixlen
    else:
        # Calculate the number of host bits needed
        host_bits = math.ceil(math.log2(required_hosts))
        prefix_length = network.max_prefixlen - host_bits
    
    # Validate prefix length
    if prefix_length <= network.prefixlen:
        raise ValueError(f"Not enough space in network {network} to accommodate {num_ip_addresses} IP addresses")
        
    if prefix_length > network.max_prefixlen:
        raise ValueError(f"Calculated prefix length ({prefix_length}) is invalid for this network type")
    
    # Initialize existing subnets list if not provided
    existing_subnets = existing_subnets or []
    
    # Convert existing subnets to ipaddress objects if they're strings
    normalized_existing = []
    for subnet in existing_subnets:
        if isinstance(subnet, str):
            normalized_existing.append(ipaddress.ip_network(subnet, strict=False))
        elif isinstance(subnet, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
            normalized_existing.append(subnet)
        else:
            raise ValueError("Existing subnets must be strings or ipaddress Network objects")
    
    # Generate possible subnets and find the first available one
    for subnet in network.subnets(new_prefix=prefix_length):
        # Check if this subnet overlaps with any existing subnet
        overlap = any(subnet.overlaps(existing) for existing in normalized_existing)
        
        if not overlap:
            return subnet
            
    # If no available subnet found
    return None

# Example usage
if __name__ == "__main__":
    # Example parent network
    parent_network = "10.1.96.0/19"
    
    # Existing subnets
    existing = [
        "10.1.96.0/27",  # 64 addresses (62 usable)
        "10.1.96.64/27"  # 64 addresses (62 usable)
    ]
    
    # Try to generate a subnet with 30 IP addresses
    new_subnet = generate_subnet(parent_network, 59, existing)
    
    if new_subnet:
        print(f"Successfully generated subnet: {new_subnet}")
        print(f"This subnet can accommodate {new_subnet.num_addresses} IP addresses "
                f"({new_subnet.num_addresses - 2} usable)")
    else:
        print("Could not generate a non-overlapping subnet")
