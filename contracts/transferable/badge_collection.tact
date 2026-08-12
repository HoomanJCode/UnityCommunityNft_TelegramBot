/// TEP-62 transferable badge collection + item.
///
/// Mint body layout MUST match the one produced by `backend/services/ton.py`:
///   op:uint32(1), query_id:uint64, index:uint64, amount:coins,
///   owner:address, common_content:ref, forward_payload:ref

import "@stdlib/ownable";

/// Mint a badge directly to `owner`.
message(0x00000001) Mint {
    query_id: Int as uint64 = 0;
    index: Int as uint64;
    amount: Int as coins;
    owner: Address;
    common_content: Cell;
    forward_payload: Cell;
}

/// TEP-62 transfer op (item ownership transfer).
message(0x5fcc3d14) Transfer {
    query_id: Int as uint64;
    new_owner: Address;
    response_destination: Address;
    custom_payload: Cell?;
    forward_amount: Int as coins;
    forward_payload: Slice as remaining;
}

message(0x05138d91) OwnershipAssigned {
    query_id: Int as uint64;
    prev_owner: Address;
}

message(0x4eb48f4d) Excesses {
    query_id: Int as uint64;
}

/// TEP-62 get_nft_data return: (init, index, collection_address, owner, content)
/// Tact flattens a struct onto the TVM stack, so this stays spec-compatible.
struct NftData {
    init_flag: Int;
    index: Int;
    collection: Address;
    owner: Address;
    content: Cell;
}

/// TEP-62 get_collection_data return: (next_item_index, collection_content, owner)
struct CollectionData {
    next_item_index: Int;
    content: Cell;
    owner: Address;
}

contract BadgeItem {
    index: Int as uint64;
    collection: Address;
    owner: Address;
    content: Cell;

    init(index: Int, collection: Address, owner: Address, content: Cell) {
        self.index = index;
        self.collection = collection;
        self.owner = owner;
        self.content = content;
    }

    /// TEP-62 transfer — only the current owner may transfer the badge.
    receive(msg: Transfer) {
        require(sender() == self.owner, "Only owner can transfer");
        let prevOwner: Address = self.owner;
        self.owner = msg.new_owner;

        // Notify the new owner, appending the forward payload to the body.
        if (msg.forward_amount > 0) {
            let body: Cell = beginCell()
                .storeUint(0x05138d91, 32)
                .storeUint(msg.query_id, 64)
                .storeAddress(prevOwner)
                .storeSlice(msg.forward_payload)
                .endCell();
            send(SendParameters{
                to: self.owner,
                value: msg.forward_amount,
                mode: SendIgnoreErrors,
                body: body,
            });
        }
        // Return the remaining balance to the response destination.
        send(SendParameters{
            to: msg.response_destination,
            value: 0,
            mode: SendRemainingValue | SendIgnoreErrors,
            body: Excesses { query_id: msg.query_id }.toCell(),
        });
    }

    /// TEP-62 get_nft_data: (init, index, collection_address, owner, content)
    get fun get_nft_data(): NftData {
        return NftData{
            init_flag: 0,
            index: self.index,
            collection: self.collection,
            owner: self.owner,
            content: self.content,
        };
    }
}

contract BadgeCollection with Ownable {
    owner: Address;
    next_item_index: Int = 0;
    content: Cell;

    init(owner: Address, content: Cell) {
        self.owner = owner;
        self.content = content;
    }

    receive(msg: Mint) {
        self.requireOwner();
        require(msg.index == self.next_item_index, "Invalid item index");

        let itemContent: Cell = self.buildItemContent(msg.index, msg.common_content);

        let init: StateInit = initOf BadgeItem(msg.index, myAddress(), msg.owner, itemContent);
        let itemAddress: Address = contractAddress(init);

        // Deploy the item directly to the recipient with its initial balance.
        send(SendParameters{
            to: itemAddress,
            value: msg.amount,
            mode: SendIgnoreErrors,
            body: msg.forward_payload,
            code: init.code,
            data: init.data,
        });

        self.next_item_index = msg.index + 1;
    }

    /// TEP-62: full item content = 0x01 + collection content + individual content.
    fun buildItemContent(index: Int, individualContent: Cell): Cell {
        return beginCell()
            .storeUint(0x01, 8)
            .storeSlice(self.content.asSlice())
            .storeRef(individualContent)
            .endCell();
    }

    /// TEP-62 get_collection_data: (next_item_index, collection_content, owner)
    get fun get_collection_data(): CollectionData {
        return CollectionData{
            next_item_index: self.next_item_index,
            content: self.content,
            owner: self.owner,
        };
    }

    get fun get_nft_address_by_index(index: Int): Address {
        // Uses a placeholder item content — matches the reference TEP-62
        // implementation (actual minted items carry their own content, which
        // differs per recipient, so this is best-effort for explorers).
        let placeholder: Cell = beginCell()
            .storeUint(0x01, 8)
            .storeSlice(self.content.asSlice())
            .storeRef(emptyCell())
            .endCell();
        let init: StateInit = initOf BadgeItem(index, myAddress(), self.owner, placeholder);
        return contractAddress(init);
    }

    /// TEP-62 get_nft_content(index, individual_content)
    get fun get_nft_content(index: Int, individual_content: Cell): Cell {
        return self.buildItemContent(index, individual_content);
    }
}
