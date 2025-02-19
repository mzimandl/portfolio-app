import React from 'react';
import { AbstractSection, numberIsValid, SectionProps } from '../../common';
import { Table, TableBody, TableHead, TableContainer, TableRow, TableCell, Box, IconButton, FormControl, Select, InputLabel, MenuItem } from '@mui/material';
import TextField from '@mui/material/TextField';
import { AddBox } from '@mui/icons-material';
import { InstrumentDataRow } from '../Settings';


interface DataRow {
    date: string;
    ticker: string;
    volume: number;
    currency: string;
}

interface NewDataRow {
    date: string;
    ticker: string;
    volume: string;
    volumeValid: boolean;
}

type StakingResponse = Array<DataRow>;

interface StakingState {
    staking: Array<DataRow>;
    instruments: Array<InstrumentDataRow>;
}

interface StakingProps {}
interface NewStakingProps {
    instruments:Array<InstrumentDataRow>;
    addStaking:(newStaking: NewDataRow) => void;
}

class NewStakingTableRow extends React.Component<NewStakingProps, NewDataRow> {

    constructor(props: NewStakingProps) {
        super(props);
        this.state = {
            date: '',
            ticker: '',
            volume: '0',
            volumeValid: true,
        };
    }

    validate() {
        return !!this.state.date && !!this.state.ticker && this.state.volumeValid;
    }

    render() {
        return <TableRow>
            <TableCell>
                <TextField label="Date" variant="outlined" size='small' margin='none' fullWidth
                onChange={(e) => this.setState({date: e.target.value})}
                error={!this.state.date} />
            </TableCell>
            <TableCell>
                <FormControl fullWidth size='small'>
                    <InputLabel id="ticker-select-label">Ticker</InputLabel>
                    <Select
                        labelId='ticker-select-label'
                        value={this.state.ticker}
                        label="Ticker"
                        onChange={(e) => this.setState({ticker: e.target.value})}
                        error={!this.state.ticker}
                    >
                        {this.props.instruments
                            .filter(v => v.type === 'crypto')
                            .map(v => <MenuItem key={v.ticker} value={v.ticker}>{v.ticker}</MenuItem>)
                        }
                    </Select>
                </FormControl>
            </TableCell>
            <TableCell>
                <TextField value={this.state.volume} label="Volume" variant="outlined" size='small' margin='none' fullWidth
                onChange={(e) => this.setState({volume: e.target.value, volumeValid: numberIsValid(e.target.value)})}
                error={!this.state.volumeValid} />
            </TableCell>
            <TableCell><IconButton disabled={!this.validate()} onClick={e => this.props.addStaking(this.state)}><AddBox/></IconButton></TableCell>
        </TableRow>
    }
}

export class Staking extends AbstractSection<StakingProps, StakingState> {

    sectionName = () => 'Staking';

    constructor(props: StakingProps & SectionProps) {
        super(props);
        this.state = {
            staking: [],
            instruments: [],
        };

        this.addValue = this.addValue.bind(this);
    }

    componentDidMount() {
        super.componentDidMount();
        this.props.displayProgressBar(true)
        this.loadInstruments().then(() =>
            this.loadValues().then(() =>
                this.props.displayProgressBar(false)
            )
        );
    }

    loadInstruments = () => {
        return fetch('/instruments/list')
            .then<Array<InstrumentDataRow>>(res => res.json())
            .then(instruments => this.setState({instruments}));
    }

    loadValues = () => {
        const params = new URLSearchParams();
        // params.append('ticker', 'CEZ.PR');
        return fetch(`/staking/list?${params.toString()}`)
            .then<StakingResponse>(res => res.json())
            .then(values => this.setState({staking: values}));
    }

    addValue = (newValue: NewDataRow) => {
        this.props.displayProgressBar(true);
        fetch('/staking/new', {method: 'POST', body: JSON.stringify(newValue)})
            .then(res => {
                this.loadValues().then(() => {
                    this.props.displayProgressBar(false);
                });
            });
    }

    render() {

        return <Box>
            <TableContainer>
                <Table size="small">
                    <TableHead>
                        <NewStakingTableRow instruments={this.state.instruments} addStaking={this.addValue} />
                    </TableHead>
                    <TableBody>
                        {this.state.staking.map(
                            (item, i) => <TableRow key={i}>
                                <TableCell>{item.date}</TableCell>
                                <TableCell>{item.ticker}</TableCell>
                                <TableCell colSpan={2}>{item.volume}</TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableContainer>
        </Box>
    }
}