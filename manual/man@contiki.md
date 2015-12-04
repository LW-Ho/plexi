# Work Overview
- Architectural Overview of what is implemented
![plexi over OSI stack][plexi_architecture]
- Resources implemented
![resource extraction][plexi_resources]
- Files in which each component lives

# *plexi* resources

## CoAP Interface
![Resource mapping to **_plexi_** structures and CoAP methods][resource_interface]

## *plexi* @ Contiki 3.x

### Resource types
- **Erbium** supports only *observable* **_XOR_** *subresources* features of CoAP resources
  - **_plexi_** needs *observable* resources with *subresources*
- **Erbium** does not natively support simultaneously *time-* and *change-* triggered notifications of *observable* resources
  - **_plexi_** needs both for /rpl/dag and statistics

Explain which resources comply with those attributes and how did you implement it

### Memory allocation

### Block-wise communication
Supporting block communication and semaphores for simultaneous requests

### Errors


[plexi_architecture]: figures/plexi_architecture.png
[plexi_resources]: figures/plexi_resources.png
[resource_interface]: figures/plexi_at_node.png
