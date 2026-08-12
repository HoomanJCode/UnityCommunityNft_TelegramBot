/// TEP-85 soulbound badge collection + item (non-transferable badges).
///
/// Mint body layout MUST match the one produced by `backend/services/ton.py`:
///   op:uint32(1), query_id:uint64, index:uint64, amount:coins,
///   owner:address, common_content:ref, forward_payload:ref
///
/// Soulbound items reject every `Transfer` attempt (exit code 1020).

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

/// TEP-62 transfer op — deliberately rejected by soulbound items.
message(0x5fcc3d14) Transfer {
    query_id: Int as uint64;
    new_owner: Address;
    response_destination: Address;
    custom_payload: Cell?;
    forward_amount: Int as coins;
    forward_payload: Slice as remaining;
}

/// Exit code used when someone tries to transfer a soulbound badge.
const SoulboundNotTransferable: Int = 1020;

contract SoulboundItem {
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

    /// TEP-85: soulbound tokens are NOT transferable.
    receive(msg: Transfer) {
        throw(SoulboundNotTransferable);
    }

    /// TEP-85 get_nft_data: (init, index, collection_address, owner, content)
    get fun get_nft_data(): [Int, Int, Address, Address, Cell] {
        return [0, self.index, self.collection, self.owner, self.content];
    }
}

contract SoulboundCollection with Ownable {
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

        let init: StateInit = initOf SoulboundItem(msg.index, myAddress(), msg.owner, itemContent);
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

    fun buildItemContent(index: Int, individualContent: Cell): Cell {
        return beginCell()
            .storeUint(0x01, 8)
            .storeSlice(self.content.asSlice())
            .storeRef(individualContent)
            .endCell();
    }

    get fun get_collection_data(): [Int, Cell, Address] {
        return [self.next_item_index, self.content, self.owner];
    }

    get fun get_nft_address_by_index(index: Int): Address {
        let placeholder: Cell = beginCell()
            .storeUint(0x01, 8)
            .storeSlice(self.content.asSlice())
            .storeRef(emptyCell())
            .endCell();
        let init: StateInit = initOf SoulboundItem(index, myAddress(), self.owner, placeholder);
        return contractAddress(init);
    }

    get fun get_nft_content(index: Int, individual_content: Cell): Cell {
        return self.buildItemContent(index, individual_content);
    }
}
