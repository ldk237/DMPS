import time
from storage_virtual_network import StorageVirtualNetwork
from storage_virtual_node import StorageVirtualNode

def format_bytes(n):
    # human-readable byte formatting
    for unit in ['B','KB','MB','GB','TB']:
        if n < 1024.0:
            return f"{n:.2f}{unit}"
        n /= 1024.0
    return f"{n:.2f}PB"

def ascii_progress_bar(completed, total, width=30):
    if total == 0:
        return "[No data]"
    ratio = completed / total
    filled = int(ratio * width)
    return "[" + "#" * filled + "-" * (width - filled) + f"] {ratio*100:6.2f}%"

def main():
    # Create network and nodes with IPs
    network = StorageVirtualNetwork()
    node1 = StorageVirtualNode("node1", cpu_capacity=4, memory_capacity=16, storage_capacity=500, bandwidth=1000, ip_address="10.0.0.1")
    node2 = StorageVirtualNode("node2", cpu_capacity=8, memory_capacity=32, storage_capacity=1000, bandwidth=2000, ip_address="10.0.0.2")
    network.add_node(node1)
    network.add_node(node2)
    network.connect_nodes("node1", "node2", bandwidth=1000)  # in Mbps

    # Initiate transfer (100 MB)
    file_size = 100 * 1024 * 1024
    transfer = network.initiate_file_transfer("node1", "node2", "large_dataset.zip", file_size)
    if not transfer:
        print("Échec : impossible d'initier le transfert (espace?)")
        return

    print(f"Transfert lancé : {transfer.file_id}")
    print(f"Source: {node1.node_id} ({node1.ip_address}) -> Cible: {node2.node_id} ({node2.ip_address})")
    total_chunks = len(transfer.chunks)
    print(f"Taille: {format_bytes(file_size)} découpée en {total_chunks} chunks")

    transferred_chunks = 0
    step = 0
    # boucle de simulation
    while True:
        step += 1
        chunks_done, completed = network.process_file_transfer("node1", "node2", transfer.file_id, chunks_per_step=3)
        transferred_chunks += chunks_done

        # Affichage "animation"
        bar = ascii_progress_bar(transferred_chunks, total_chunks, width=40)
        stats = network.get_network_stats()
        node2_storage = node2.get_storage_utilization()
        node2_net = node2.get_network_utilization()
        print(f"Step {step:03d} | {bar} | chunks step: {chunks_done} | transfers active: {stats['active_transfers']}")
        print(f"  Network util: {stats['bandwidth_utilization']:.2f}% | Node2 net util: {node2_net['utilization_percent']:.2f}%")
        print(f"  Node2 storage: {format_bytes(node2_storage['used_bytes'])} / {format_bytes(node2_storage['total_bytes'])} ({node2_storage['utilization_percent']:.4f}%)")
        print("-" * 100)

        if completed:
            print("Transfert terminé avec succès !")
            break

        # petite pause pour lisibilité
        time.sleep(0.15)

if __name__ == "__main__":
    main()